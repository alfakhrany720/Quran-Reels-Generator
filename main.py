# Quran Reels Generator - Backend Server
# This script provides the video generation API for the HTML UI

import os
import sys
import shutil
import random
import threading
import webbrowser
import json
import datetime
import logging
import traceback

from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS


# ============================================================
# Path Resolution Functions
# ============================================================

def app_dir():
    """Returns the directory of the executable (or script)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def bundled_dir():
    """Returns the bundled temp directory or script directory."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


# ============================================================
# Base Directories
# ============================================================

EXEC_DIR = app_dir()
BUNDLE_DIR = bundled_dir()


# ============================================================
# Logging
# ============================================================

log_path = os.path.join(EXEC_DIR, "runlog.txt")

logging.basicConfig(
    filename=log_path,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    force=True
)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
logging.getLogger().addHandler(console_handler)

logging.info("--- Starting Quran Reels Generator ---")
logging.info(f"Execution Directory: {EXEC_DIR}")
logging.info(f"Bundled Directory: {BUNDLE_DIR}")


# ============================================================
# Linux Binary Paths
# ============================================================

# FFmpeg
FFMPEG_EXE = shutil.which("ffmpeg") or "/usr/bin/ffmpeg"

# ImageMagick
# New ImageMagick versions may expose "magick",
# while Debian/Ubuntu may expose "convert".
IM_MAGICK_EXE = (
    shutil.which("magick")
    or shutil.which("convert")
    or "/usr/bin/convert"
)

# Linux system directory
IM_HOME = "/usr"


# ============================================================
# Project Paths
# ============================================================

VISION_DIR = os.path.join(BUNDLE_DIR, "vision")
UI_PATH = os.path.join(BUNDLE_DIR, "UI.html")

OUT_DIR = os.path.join(EXEC_DIR, "outputs")
AUDIO_DIR = os.path.join(OUT_DIR, "audio")
VIDEO_DIR = os.path.join(OUT_DIR, "video")

FONT_DIR = os.path.join(EXEC_DIR, "fonts")

FONT_PATH = os.path.join(
    FONT_DIR,
    "DUBAI-MEDIUM.TTF"
)

# Prefer the Quran-specific Amiri font installed in the Linux container.
# It supports Quranic annotation marks that the Dubai font may not contain.
# Quran text MUST use a Quran-capable font.
# Do not silently fall back to Dubai/DejaVu because those fonts
# can show Quranic annotation marks as square boxes.
ARABIC_FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/fonts-hosny-amiri/AmiriQuran.ttf",
    "/usr/share/fonts/opentype/fonts-hosny-amiri/AmiriQuranColored.ttf",
    "/usr/share/fonts/opentype/fonts-hosny-amiri/Amiri-Regular.ttf",
    "/usr/share/fonts/truetype/amiri/AmiriQuran.ttf",
    "/usr/share/fonts/truetype/amiri/Amiri-Regular.ttf",
    os.path.join(FONT_DIR, "AmiriQuran.ttf"),
    os.path.join(FONT_DIR, "Amiri-Regular.ttf"),
]

FONT_PATH_ARABIC = next(
    (
        path
        for path in ARABIC_FONT_CANDIDATES
        if os.path.isfile(path)
    ),
    None
)

if not FONT_PATH_ARABIC:
    raise RuntimeError(
        "Quran font not found. Expected AmiriQuran.ttf. "
        "Install Debian package fonts-hosny-amiri."
    )

logging.info(
    f"QURAN FONT SELECTED: {FONT_PATH_ARABIC}"
)

FONT_PATH_ENGLISH = os.path.join(
    FONT_DIR,
    "DUBAI-REGULAR.TTF"
)


# ============================================================
# Create Required Folders
# ============================================================

try:
    os.makedirs(AUDIO_DIR, exist_ok=True)
    os.makedirs(VIDEO_DIR, exist_ok=True)
    os.makedirs(FONT_DIR, exist_ok=True)

    logging.info("Output and Font directories verified.")

except Exception as e:
    logging.error(
        f"Failed to create directories: {e}"
    )


# ============================================================
# Validate Required Files
# ============================================================

if not os.path.isfile(FFMPEG_EXE):
    logging.error(
        f"Missing ffmpeg at {FFMPEG_EXE}"
    )

if not os.path.isfile(IM_MAGICK_EXE):
    logging.error(
        f"Missing ImageMagick executable at {IM_MAGICK_EXE}"
    )

if not os.path.isdir(VISION_DIR):
    logging.error(
        f"Missing vision folder at {VISION_DIR}"
    )

if not os.path.isfile(UI_PATH):
    logging.error(
        f"Missing UI.html at {UI_PATH}"
    )


# ============================================================
# Environment Variables
# ============================================================

os.environ["FFMPEG_BINARY"] = FFMPEG_EXE
os.environ["IMAGEIO_FFMPEG_EXE"] = FFMPEG_EXE

# ImageMagick
os.environ["IMAGEMAGICK_BINARY"] = IM_MAGICK_EXE
os.environ["MAGICK_HOME"] = IM_HOME

# ImageMagick configuration
# Different Linux distributions may use different paths.
possible_config_paths = [
    "/etc/ImageMagick-6",
    "/etc/ImageMagick-7",
    "/usr/lib/ImageMagick-6.9.11/config-Q16",
    "/usr/share/ImageMagick-6",
    "/usr/share/ImageMagick-7",
]

for config_path in possible_config_paths:
    if os.path.exists(config_path):
        os.environ["MAGICK_CONFIGURE_PATH"] = config_path
        break

# ImageMagick coder modules
possible_coder_paths = [
    "/usr/lib/ImageMagick-6.9.11/modules-Q16/coders",
    "/usr/lib/x86_64-linux-gnu/ImageMagick-6.9.11/modules-Q16/coders",
    "/usr/lib/ImageMagick-7/modules-Q16/coders",
    "/usr/lib/x86_64-linux-gnu/ImageMagick-7/modules-Q16/coders",
]

for coder_path in possible_coder_paths:
    if os.path.exists(coder_path):
        os.environ["MAGICK_CODER_MODULE_PATH"] = coder_path
        break


# ============================================================
# PATH
# ============================================================

current_path = os.environ.get("PATH", "")

os.environ["PATH"] = os.pathsep.join([
    "/usr/bin",
    "/usr/local/bin",
    os.path.dirname(FFMPEG_EXE),
    os.path.dirname(IM_MAGICK_EXE),
    current_path
])


logging.info(
    "Environment variables configured for Linux binaries."
)


# ============================================================
# Python Dependencies
# ============================================================

import requests as http_requests

from pydub import AudioSegment

AudioSegment.converter = FFMPEG_EXE
AudioSegment.ffmpeg = FFMPEG_EXE

AudioSegment.ffprobe = (
    shutil.which("ffprobe")
    or "/usr/bin/ffprobe"
)


# ============================================================
# MoviePy Configuration
# ============================================================

from moviepy.config import change_settings

try:

    change_settings({
        "FFMPEG_BINARY": FFMPEG_EXE,
        "IMAGEMAGICK_BINARY": IM_MAGICK_EXE
    })

    logging.info(
        f"MoviePy FFmpeg: {FFMPEG_EXE}"
    )

    logging.info(
        f"MoviePy ImageMagick: {IM_MAGICK_EXE}"
    )

except Exception as e:

    logging.error(
        f"MoviePy config error: {e}"
    )


from moviepy.editor import (
    VideoFileClip,
    AudioFileClip,
    ImageClip,
    CompositeVideoClip,
    concatenate_videoclips
)

import moviepy.video.fx.all as vfx

from PIL import Image, ImageDraw, ImageFont, features
import arabic_reshaper
from bidi.algorithm import get_display
import numpy as np


# ============================================================
# Verse Counts
# ============================================================

VERSE_COUNTS = {

    1: 7,
    2: 286,
    3: 200,
    4: 176,
    5: 120,
    6: 165,
    7: 206,
    8: 75,
    9: 129,
    10: 109,

    11: 123,
    12: 111,
    13: 43,
    14: 52,
    15: 99,
    16: 128,
    17: 111,
    18: 110,
    19: 98,
    20: 135,

    21: 112,
    22: 78,
    23: 118,
    24: 64,
    25: 77,
    26: 227,
    27: 93,
    28: 88,
    29: 69,
    30: 60,

    31: 34,
    32: 30,
    33: 73,
    34: 54,
    35: 45,
    36: 83,
    37: 182,
    38: 88,
    39: 75,
    40: 85,

    41: 54,
    42: 53,
    43: 89,
    44: 59,
    45: 37,
    46: 35,
    47: 38,
    48: 29,
    49: 18,
    50: 45,

    51: 60,
    52: 49,
    53: 62,
    54: 55,
    55: 78,
    56: 96,
    57: 29,
    58: 22,
    59: 24,
    60: 13,

    61: 14,
    62: 11,
    63: 11,
    64: 18,
    65: 12,
    66: 12,
    67: 30,
    68: 52,
    69: 52,
    70: 44,

    71: 28,
    72: 28,
    73: 20,
    74: 56,
    75: 40,
    76: 31,
    77: 50,
    78: 40,
    79: 46,
    80: 42,

    81: 29,
    82: 19,
    83: 36,
    84: 25,
    85: 22,
    86: 17,
    87: 19,
    88: 26,
    89: 30,
    90: 20,

    91: 15,
    92: 21,
    93: 11,
    94: 8,
    95: 8,
    96: 19,
    97: 5,
    98: 8,
    99: 8,
    100: 11,

    101: 11,
    102: 8,
    103: 3,
    104: 9,
    105: 5,
    106: 4,
    107: 7,
    108: 3,
    109: 6,
    110: 3,

    111: 5,
    112: 4,
    113: 5,
    114: 6
}


# ============================================================
# Surah Names
# ============================================================

SURAH_NAMES = [

    'الفاتحة',
    'البقرة',
    'آل عمران',
    'النساء',
    'المائدة',
    'الأنعام',
    'الأعراف',
    'الأنفال',
    'التوبة',
    'يونس',

    'هود',
    'يوسف',
    'الرعد',
    'إبراهيم',
    'الحجر',
    'النحل',
    'الإسراء',
    'الكهف',
    'مريم',
    'طه',

    'الأنبياء',
    'الحج',
    'المؤمنون',
    'النور',
    'الفرقان',
    'الشعراء',
    'النمل',
    'القصص',
    'العنكبوت',
    'الروم',

    'لقمان',
    'السجدة',
    'الأحزاب',
    'سبأ',
    'فاطر',
    'يس',
    'الصافات',
    'ص',
    'الزمر',
    'غافر',

    'فصلت',
    'الشورى',
    'الزخرف',
    'الدخان',
    'الجاثية',
    'الأحقاف',
    'محمد',
    'الفتح',
    'الحجرات',
    'ق',

    'الذاريات',
    'الطور',
    'النجم',
    'القمر',
    'الرحمن',
    'الواقعة',
    'الحديد',
    'المجادلة',
    'الحشر',
    'الممتحنة',

    'الصف',
    'الجمعة',
    'المنافقون',
    'التغابن',
    'الطلاق',
    'التحريم',
    'الملك',
    'القلم',
    'الحاقة',
    'المعارج',

    'نوح',
    'الجن',
    'المزمل',
    'المدثر',
    'القيامة',
    'الإنسان',
    'المرسلات',
    'النبأ',
    'النازعات',
    'عبس',

    'التكوير',
    'الانفطار',
    'المطففين',
    'الانشقاق',
    'البروج',
    'الطارق',
    'الأعلى',
    'الغاشية',
    'الفجر',
    'البلد',

    'الشمس',
    'الليل',
    'الضحى',
    'الشرح',
    'التين',
    'العلق',
    'القدر',
    'البينة',
    'الزلزلة',
    'العاديات',

    'القارعة',
    'التكاثر',
    'العصر',
    'الهمزة',
    'الفيل',
    'قريش',
    'الماعون',
    'الكوثر',
    'الكافرون',
    'النصر',

    'المسد',
    'الإخلاص',
    'الفلق',
    'الناس'
]


# ============================================================
# Reciters
# ============================================================

RECITERS_MAP = {

    'الشيخ عبدالباسط عبدالصمد':
        'AbdulSamad_64kbps_QuranExplorer.Com',

    'الشيخ عبدالباسط عبدالصمد (مرتل)':
        'Abdul_Basit_Murattal_64kbps',

    'الشيخ عبدالرحمن السديس':
        'Abdurrahmaan_As-Sudais_64kbps',

    'الشيخ ماهر المعيقلي':
        'Maher_AlMuaiqly_64kbps',

    'الشيخ محمد صديق المنشاوي (مجود)':
        'Minshawy_Mujawwad_64kbps',

    'الشيخ سعود الشريم':
        'Saood_ash-Shuraym_64kbps',

    'الشيخ مشاري العفاسي':
        'Alafasy_64kbps',

    'الشيخ محمود خليل الحصري':
        'Husary_64kbps',

    'الشيخ عبدالله الحذيفي':
        'Hudhaify_64kbps',

    'الشيخ أبو بكر الشاطري':
        'Abu_Bakr_Ash-Shaatree_128kbps',

    'الشيخ محمود علي البنا':
        'mahmoud_ali_al_banna_32kbps'
}


# ============================================================
# Global Progress Tracking
# ============================================================

current_progress = {

    'percent': 0,

    'status':
        'جاري التحضير...',

    'log':
        [],

    'is_running':
        False,

    'is_complete':
        False,

    'output_path':
        None,

    'error':
        None
}


# ============================================================
# Flask Application
# ============================================================

app = Flask(
    __name__,
    static_folder=EXEC_DIR
)

CORS(app)


# ============================================================
# Progress Functions
# ============================================================

def reset_progress():

    global current_progress

    current_progress = {

        'percent': 0,

        'status':
            'جاري التحضير...',

        'log':
            [],

        'is_running':
            False,

        'is_complete':
            False,

        'output_path':
            None,

        'error':
            None
    }


def add_log(message):

    current_progress['log'].append(message)

    logging.info(
        f"PROGRESS: {message}"
    )

    print(
        f">>> {message}",
        flush=True
    )


def update_progress(percent, status):

    current_progress['percent'] = percent

    current_progress['status'] = status

    logging.info(
        f"STATUS ({percent}%): {status}"
    )


# ============================================================
# Output Management
# ============================================================

def clear_outputs():

    # Only clear audio directory
    # Keep generated video history.

    if os.path.isdir(AUDIO_DIR):

        try:

            shutil.rmtree(
                AUDIO_DIR
            )

            os.makedirs(
                AUDIO_DIR,
                exist_ok=True
            )

        except Exception as e:

            logging.error(
                f"Error clearing audio output: {e}"
            )


# ============================================================
# Audio Helpers
# ============================================================

def detect_leading_silence(
    sound,
    thresh,
    chunk=10
):

    t = 0

    while (
        t < len(sound)
        and sound[t:t + chunk].dBFS < thresh
    ):

        t += chunk

    return t


def detect_trailing_silence(
    sound,
    thresh,
    chunk=10
):

    return detect_leading_silence(
        sound.reverse(),
        thresh,
        chunk
    )


# ============================================================
# Download Quran Audio
# ============================================================

def download_audio(
    reciter_id,
    surah,
    ayah,
    idx
):

    os.makedirs(
        AUDIO_DIR,
        exist_ok=True
    )

    fn = f'{surah:03d}{ayah:03d}.mp3'

    url = (
        f'https://everyayah.com/data/'
        f'{reciter_id}/{fn}'
    )

    out = os.path.join(
        AUDIO_DIR,
        f'part{idx}.mp3'
    )

    r = http_requests.get(
        url,
        timeout=60
    )

    r.raise_for_status()

    with open(
        out,
        'wb'
    ) as f:

        f.write(
            r.content
        )

    snd = AudioSegment.from_file(
        out,
        'mp3'
    )

    start = detect_leading_silence(
        snd,
        snd.dBFS - 16
    )

    end = detect_trailing_silence(
        snd,
        snd.dBFS - 16
    )

    trimmed = snd[
        start:
        len(snd) - end
    ]

    trimmed.export(
        out,
        format='mp3'
    )

    return out


# ============================================================
# Quran Text
# ============================================================

def get_ayah_text(
    surah,
    ayah
):

    try:

        resp = http_requests.get(
            f'https://api.alquran.cloud/v1/'
            f'ayah/{surah}:{ayah}/quran-uthmani',
            timeout=60
        )

        resp.raise_for_status()

        return resp.json()[
            'data'
        ][
            'text'
        ]

    except Exception as e:

        logging.error(
            f"Failed to fetch ayah text: {e}"
        )

        raise


# ============================================================
# Text Wrapping
# ============================================================

def wrap_text(
    text,
    per_line
):

    """Wrap text into multiple lines."""

    words = text.split()

    lines = [

        ' '.join(
            words[i:i + per_line]
        )

        for i in range(
            0,
            len(words),
            per_line
        )
    ]

    return '\n'.join(lines)


# ============================================================
# Create Arabic Text Clip
# ============================================================

def create_text_clip(
    arabic,
    duration,
    video_width=1080,
    video_height=1920
):
    """
    Render Quranic Arabic text reliably.

    Priority:
    1) Pillow + libraqm/Harfbuzz RTL shaping, if available.
    2) arabic_reshaper + python-bidi fallback.

    The Quran-specific AmiriQuran font is mandatory.
    """

    if not arabic:
        return ImageClip(
            np.zeros((1, 1, 4), dtype=np.uint8)
        ).set_duration(duration)

    if not FONT_PATH_ARABIC:
        raise RuntimeError("No Quran font is available.")

    words = arabic.split()

    max_text_width = int(video_width * 0.88)
    max_text_height = int(video_height * 0.44)

    # Prefer RAQM when Pillow has it. This is the cleanest route
    # for Arabic shaping and Quranic combining marks.
    try:
        use_raqm = bool(features.check("raqm"))
    except Exception:
        use_raqm = False

    logging.info(
        f"Quran renderer: font={FONT_PATH_ARABIC}, "
        f"raqm={use_raqm}"
    )

    def prepare_text(text):
        if use_raqm:
            return text
        # Fallback only when RAQM is unavailable.
        return get_display(
            arabic_reshaper.reshape(text)
        )

    def text_kwargs():
        if use_raqm:
            return {
                "direction": "rtl",
                "language": "ar"
            }
        return {}

    dummy = Image.new(
        "RGBA",
        (video_width, video_height),
        (0, 0, 0, 0)
    )
    measure_draw = ImageDraw.Draw(dummy)

    def measure(text, font):
        visual = prepare_text(text)
        bbox = measure_draw.textbbox(
            (0, 0),
            visual,
            font=font,
            stroke_width=1,
            **text_kwargs()
        )
        return (
            visual,
            bbox[2] - bbox[0],
            bbox[3] - bbox[1]
        )

    selected = None

    # Long enough range to guarantee the complete ayah fits.
    for fontsize in range(48, 27, -2):

        font = ImageFont.truetype(
            FONT_PATH_ARABIC,
            fontsize
        )

        lines = []
        current_words = []

        # Wrap using the real rendered width.
        for word in words:

            candidate_words = current_words + [word]
            candidate = " ".join(candidate_words)

            _, candidate_width, _ = measure(
                candidate,
                font
            )

            if (
                current_words
                and candidate_width > max_text_width
            ):
                lines.append(
                    " ".join(current_words)
                )
                current_words = [word]
            else:
                current_words = candidate_words

        if current_words:
            lines.append(
                " ".join(current_words)
            )

        visual_lines = []
        line_gap = max(
            8,
            int(fontsize * 0.18)
        )
        total_height = 0
        fits = True

        for line in lines:

            visual, width, height = measure(
                line,
                font
            )

            if width > max_text_width:
                fits = False
                break

            visual_lines.append(
                (visual, width, height)
            )

            total_height += height

        total_height += (
            line_gap * max(
                0,
                len(visual_lines) - 1
            )
        )

        # Never allow the text to become a huge block.
        if (
            fits
            and visual_lines
            and total_height <= max_text_height
            and len(visual_lines) <= 10
        ):
            selected = (
                font,
                visual_lines,
                total_height,
                line_gap
            )
            break

    if selected is None:
        # Final guaranteed-safe size.
        font = ImageFont.truetype(
            FONT_PATH_ARABIC,
            28
        )

        lines = []
        current_words = []

        for word in words:

            candidate = " ".join(
                current_words + [word]
            )

            _, width, _ = measure(
                candidate,
                font
            )

            if (
                current_words
                and width > max_text_width
            ):
                lines.append(
                    " ".join(current_words)
                )
                current_words = [word]
            else:
                current_words.append(word)

        if current_words:
            lines.append(
                " ".join(current_words)
            )

        visual_lines = []

        for line in lines:
            visual, width, height = measure(
                line,
                font
            )
            visual_lines.append(
                (visual, width, height)
            )

        line_gap = 8
        total_height = (
            sum(
                h
                for _, _, h in visual_lines
            )
            + line_gap * max(
                0,
                len(visual_lines) - 1
            )
        )

        selected = (
            font,
            visual_lines,
            total_height,
            line_gap
        )

    font, visual_lines, total_height, line_gap = selected

    padding_x = 24
    padding_y = 24

    canvas_height = (
        total_height
        + padding_y * 2
    )

    img = Image.new(
        "RGBA",
        (
            video_width,
            canvas_height
        ),
        (0, 0, 0, 0)
    )

    draw = ImageDraw.Draw(img)

    y = padding_y

    for visual, width, height in visual_lines:

        x = (
            video_width - width
        ) // 2

        draw.text(
            (x, y),
            visual,
            font=font,
            fill=(255, 255, 255, 255),
            stroke_width=2,
            stroke_fill=(0, 0, 0, 255),
            **text_kwargs()
        )

        y += height + line_gap

    frame = np.array(img)

    return (
        ImageClip(frame)
        .set_duration(duration)
        .set_position(("center", "center"))
    )


# ============================================================
# Pick Background
# ============================================================

def pick_bg():

    try:

        files = [

            f

            for f in os.listdir(
                VISION_DIR
            )

            if (
                f.startswith('nature_part')
                and f.endswith('.mp4')
            )
        ]

        if not files:

            logging.error(
                "No bg videos found in vision folder!"
            )

            raise ValueError(
                "No background videos found."
            )

        return os.path.join(
            VISION_DIR,
            random.choice(files)
        )

    except Exception as e:

        logging.error(
            f"Error picking background: {e}"
        )

        raise


# ============================================================
# Build Video
# ============================================================

def build_video(
    reciter_id,
    surah,
    start_ayah,
    end_ayah=None
):

    """
    Build video from start_ayah to end_ayah.

    If end_ayah is None,
    it defaults to start_ayah + 9
    or max ayah of surah.
    """

    global current_progress

    try:

        current_progress[
            'is_running'
        ] = True

        current_progress[
            'is_complete'
        ] = False

        current_progress[
            'error'
        ] = None

        # ----------------------------------------------------
        # Step 1
        # ----------------------------------------------------

        add_log(
            '[1] Clearing output folders...'
        )

        update_progress(
            5,
            'جاري تنظيف ملفات الإخراج...'
        )

        clear_outputs()

        # ----------------------------------------------------
        # Verse Range
        # ----------------------------------------------------

        max_ayah = VERSE_COUNTS[
            surah
        ]

        if end_ayah is None:

            last_ayah = min(
                start_ayah + 9,
                max_ayah
            )

        else:

            last_ayah = min(
                end_ayah,
                max_ayah
            )

        if last_ayah < start_ayah:

            last_ayah = start_ayah

        total = (
            last_ayah
            - start_ayah
            + 1
        )

        # ----------------------------------------------------
        # Step 2
        # ----------------------------------------------------

        add_log(
            f'[2] Preparing {total} '
            f'آيات (from {start_ayah} '
            f'to {last_ayah})'
        )

        update_progress(
            10,
            f'جاري تحضير {total} آيات...'
        )

        clips = []

        # ----------------------------------------------------
        # Process Each Ayah
        # ----------------------------------------------------

        for idx, ayah in enumerate(
            range(
                start_ayah,
                last_ayah + 1
            ),
            start=1
        ):

            progress_per_ayah = (
                70 / total
            )

            base_progress = (
                10
                + (idx - 1)
                * progress_per_ayah
            )

            # -----------------------------------------------
            # Download Audio
            # -----------------------------------------------

            add_log(
                f'[3.{idx}] '
                f'Downloading audio '
                f'for آية {ayah}'
            )

            update_progress(
                int(
                    base_progress
                    + progress_per_ayah * 0.3
                ),
                f'جاري تحميل صوت الآية '
                f'{ayah}...'
            )

            ap = download_audio(
                reciter_id,
                surah,
                ayah,
                idx - 1
            )

            # -----------------------------------------------
            # Fetch Text
            # -----------------------------------------------

            add_log(
                f'[3.{idx}] Fetching texts'
            )

            update_progress(
                int(
                    base_progress
                    + progress_per_ayah * 0.5
                ),
                f'جاري جلب نص الآية '
                f'{ayah}...'
            )

            ar = get_ayah_text(
                surah,
                ayah
            )

            # -----------------------------------------------
            # Audio
            # -----------------------------------------------

            audio_clip = AudioFileClip(
                ap
            )

            dur = audio_clip.duration

            audio = (
                audio_clip
                .audio_fadein(0.2)
                .audio_fadeout(0.2)
            )

            # -----------------------------------------------
            # Build Segment
            # -----------------------------------------------

            add_log(
                f'[3.{idx}] Building segment'
            )

            update_progress(
                int(
                    base_progress
                    + progress_per_ayah * 0.8
                ),
                f'جاري إنشاء مقطع الآية '
                f'{ayah}...'
            )

            bg_path = pick_bg()

            bg = VideoFileClip(
                bg_path
            )

            seg_bg = (
                bg.fx(
                    vfx.loop,
                    duration=dur
                )
                .subclip(
                    0,
                    dur
                )
            )

            ar_clip = create_text_clip(
                ar,
                dur
            )

            seg = (
                CompositeVideoClip(
                    [
                        seg_bg,
                        ar_clip
                    ]
                )
                .set_audio(audio)
            )

            clips.append(
                seg
            )

        # ----------------------------------------------------
        # Concatenate
        # ----------------------------------------------------

        add_log(
            '[4] Concatenating segments...'
        )

        update_progress(
            85,
            'جاري دمج المقاطع...'
        )

        final = concatenate_videoclips(
            clips,
            method='compose'
        )

        # ----------------------------------------------------
        # Output Filename
        # ----------------------------------------------------

        timestamp = datetime.datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        surah_name = SURAH_NAMES[
            surah - 1
        ]

        filename = (
            f"QuranReel_"
            f"{surah_name}_"
            f"{start_ayah}-"
            f"{last_ayah}_"
            f"{timestamp}.mp4"
        )

        out = os.path.join(
            VIDEO_DIR,
            filename
        )

        # ----------------------------------------------------
        # Write Video
        # ----------------------------------------------------

        add_log(
            f'[5] Writing final video → {out}'
        )

        update_progress(
            90,
            'جاري كتابة الفيديو النهائي...'
        )

        final.write_videofile(

            out,

            fps=24,

            codec='libx264',

            audio_codec='aac',

            audio_bitrate='192k',

            verbose=False,

            ffmpeg_params=[
                '-movflags',
                '+faststart'
            ]
        )

        # ----------------------------------------------------
        # Done
        # ----------------------------------------------------

        add_log(
            '[6] Done!'
        )

        update_progress(
            100,
            'تم بنجاح!'
        )

        current_progress[
            'is_complete'
        ] = True

        current_progress[
            'output_path'
        ] = out

        # Close clips
        try:

            final.close()

        except Exception:

            pass

        for clip in clips:

            try:

                clip.close()

            except Exception:

                pass

    except Exception as e:

        logger_error_msg = (
            f"Error in build_video: "
            f"{str(e)}\n"
            f"{traceback.format_exc()}"
        )

        logging.error(
            logger_error_msg
        )

        current_progress[
            'error'
        ] = str(e)

        add_log(
            f'[ERROR] {str(e)}'
        )

        update_progress(
            0,
            f'خطأ: {str(e)}'
        )

    finally:

        current_progress[
            'is_running'
        ] = False


# ============================================================
# API Routes
# ============================================================

@app.route('/')
def serve_ui():

    if os.path.exists(
        UI_PATH
    ):

        return send_file(
            UI_PATH
        )

    else:

        return (
            f"Error: UI.html not found "
            f"at {UI_PATH}"
        ), 404


# ============================================================
# Generate Video API
# ============================================================

@app.route(
    '/api/generate',
    methods=['POST']
)
def generate_video():

    global current_progress

    if current_progress[
        'is_running'
    ]:

        return jsonify({
            'error':
                'عملية إنشاء فيديو '
                'قيد التنفيذ بالفعل'
        }), 400

    data = request.json

    if not data:

        return jsonify({
            'error':
                'No JSON data received'
        }), 400

    reciter_id = data.get(
        'reciter'
    )

    surah = int(
        data.get(
            'surah',
            1
        )
    )

    start_ayah = int(
        data.get(
            'startAyah',
            1
        )
    )

    end_ayah = data.get(
        'endAyah'
    )

    if end_ayah is not None:

        end_ayah = int(
            end_ayah
        )

    reset_progress()

    # Start video generation
    # in background thread.

    thread = threading.Thread(

        target=build_video,

        args=(
            reciter_id,
            surah,
            start_ayah,
            end_ayah
        ),

        daemon=True
    )

    thread.start()

    return jsonify({
        'success':
            True,

        'message':
            'بدأ إنشاء الفيديو'
    })


# ============================================================
# Progress API
# ============================================================

@app.route(
    '/api/progress',
    methods=['GET']
)
def get_progress():

    return jsonify(
        current_progress
    )


# ============================================================
# Configuration API
# ============================================================

@app.route(
    '/api/config',
    methods=['GET']
)
def get_config():

    return jsonify({

        'surahs':
            SURAH_NAMES,

        'verseCounts':
            VERSE_COUNTS,

        'reciters':
            RECITERS_MAP
    })


# ============================================================
# Output Video
# ============================================================

@app.route(
    '/outputs/<path:filename>'
)
def serve_output(filename):

    return send_from_directory(
        OUT_DIR,
        filename
    )


@app.route(
    '/final_video.mp4'
)
def serve_final_video():

    return send_from_directory(
        EXEC_DIR,
        'final_video.mp4'
    )


# ============================================================
# Start Server
# ============================================================

if __name__ == '__main__':

    logging.info(
        'Server Starting...'
    )

    print(
        '=' * 50
    )

    print(
        '  One-Click Quran Reels Generator'
    )

    print(
        '  Running in Linux Server Mode'
    )

    print(
        '=' * 50
    )

    # Start Flask server.
    # 0.0.0.0 is required when running
    # inside a Docker/Coolify container.

    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False,
        threaded=True
    )
