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

# --- Step: Path Resolution Functions ---
def app_dir():
    """Returns the directory of the executable (or script) - Use for external files (fonts, outputs, logs)"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def bundled_dir():
    """Returns the bundled temp directory or script dir - Use for internal assets (bin, vision, UI)"""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

# --- Step: Define Base Directories ---
EXEC_DIR = app_dir()
BUNDLE_DIR = bundled_dir()

# --- Step: Setup Logging ---
log_path = os.path.join(EXEC_DIR, "runlog.txt")
logging.basicConfig(filename=log_path, level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s', force=True)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
logging.getLogger().addHandler(console_handler)

logging.info("--- Starting Quran Reels Generator ---")
logging.info(f"Execution Directory: {EXEC_DIR}")
logging.info(f"Bundled Directory: {BUNDLE_DIR}")

# --- Step: Define Paths ---
FFMPEG_EXE = shutil.which("ffmpeg") or "/usr/bin/ffmpeg"
IM_MAGICK_EXE = shutil.which("magick") or "/usr/bin/magick"
IM_HOME = "/usr"

VISION_DIR = os.path.join(BUNDLE_DIR, "vision")
UI_PATH = os.path.join(BUNDLE_DIR, "UI.html")

OUT_DIR = os.path.join(EXEC_DIR, "outputs")
AUDIO_DIR = os.path.join(OUT_DIR, "audio")
VIDEO_DIR = os.path.join(OUT_DIR, "video")

FONT_DIR = os.path.join(EXEC_DIR, "fonts")
FONT_PATH = os.path.join(FONT_DIR, "DUBAI-MEDIUM.TTF")
FONT_PATH_ARABIC = os.path.join(FONT_DIR, "DUBAI-BOLD.TTF")
FONT_PATH_ENGLISH = os.path.join(FONT_DIR, "DUBAI-REGULAR.TTF")

# Create folders on startup
try:
    os.makedirs(AUDIO_DIR, exist_ok=True)
    os.makedirs(VIDEO_DIR, exist_ok=True)
    os.makedirs(FONT_DIR, exist_ok=True)
    logging.info("Output and Font directories verified.")
except Exception as e:
    logging.error(f"Failed to create directories: {e}")

# Validate Bundled Requirements
if not os.path.isfile(FFMPEG_EXE):
    logging.error(f"Missing ffmpeg at {FFMPEG_EXE}")

if not os.path.isfile(IM_MAGICK_EXE):
    logging.error(f"Missing ImageMagick at {IM_MAGICK_EXE}")
if not os.path.isdir(VISION_DIR): logging.error(f"Missing vision folder at {VISION_DIR}")
if not os.path.isfile(UI_PATH): logging.error(f"Missing UI.html at {UI_PATH}")

# --- Step: Configure Environment Variables ---
os.environ["FFMPEG_BINARY"] = FFMPEG_EXE
os.environ["IMAGEIO_FFMPEG_EXE"] = FFMPEG_EXE

# ImageMagick Environment Setup
os.environ["IMAGEMAGICK_BINARY"] = IM_MAGICK_EXE
os.environ["MAGICK_HOME"] = IM_HOME
MAGICK_CODER_MODULE_PATH
# Pre-flight check: if config dir missing, fallback to root or modules
if not os.path.exists(os.environ["MAGICK_CONFIGURE_PATH"]):
    os.environ["MAGICK_CONFIGURE_PATH"] = IM_HOME # Portable versions often have xmls in root

os.environ["MAGICK_CODER_MODULE_PATH"] = os.path.join(IM_HOME, "modules", "coders") # Typical path
if not os.path.exists(os.environ["MAGICK_CODER_MODULE_PATH"]):
    os.environ["MAGICK_CODER_MODULE_PATH"] = os.path.join(IM_HOME, "modules")

# Prepend PATH for DLL discovery
os.environ["PATH"] = os.pathsep.join([
    os.path.dirname(FFMPEG_EXE),
    IM_HOME,
    os.environ.get("PATH", "")
])

logging.info("Environment variables set for portable binaries.")

import requests as http_requests
from pydub import AudioSegment
AudioSegment.converter = FFMPEG_EXE
AudioSegment.ffmpeg = FFMPEG_EXE
AudioSegment.ffprobe = shutil.which("ffprobe") or "/usr/bin/ffprobe"

from moviepy.config import change_settings
try:
    change_settings({"FFMPEG_BINARY": FFMPEG_EXE, "IMAGEMAGICK_BINARY": IM_MAGICK_EXE})
except Exception as e:
    logging.error(f"MoviePy config error: {e}")

from moviepy.editor import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, concatenate_videoclips
import moviepy.video.fx.all as vfx

# Verse counts for each Surah
VERSE_COUNTS = {
    1: 7, 2: 286, 3: 200, 4: 176, 5: 120, 6: 165, 7: 206, 8: 75, 9: 129, 10: 109,
    11: 123, 12: 111, 13: 43, 14: 52, 15: 99, 16: 128, 17: 111, 18: 110, 19: 98, 20: 135,
    21: 112, 22: 78, 23: 118, 24: 64, 25: 77, 26: 227, 27: 93, 28: 88, 29: 69, 30: 60,
    31: 34, 32: 30, 33: 73, 34: 54, 35: 45, 36: 83, 37: 182, 38: 88, 39: 75, 40: 85,
    41: 54, 42: 53, 43: 89, 44: 59, 45: 37, 46: 35, 47: 38, 48: 29, 49: 18, 50: 45,
    51: 60, 52: 49, 53: 62, 54: 55, 55: 78, 56: 96, 57: 29, 58: 22, 59: 24, 60: 13,
    61: 14, 62: 11, 63: 11, 64: 18, 65: 12, 66: 12, 67: 30, 68: 52, 69: 52, 70: 44,
    71: 28, 72: 28, 73: 20, 74: 56, 75: 40, 76: 31, 77: 50, 78: 40, 79: 46, 80: 42,
    81: 29, 82: 19, 83: 36, 84: 25, 85: 22, 86: 17, 87: 19, 88: 26, 89: 30, 90: 20,
    91: 15, 92: 21, 93: 11, 94: 8, 95: 8, 96: 19, 97: 5, 98: 8, 99: 8, 100: 11,
    101: 11, 102: 8, 103: 3, 104: 9, 105: 5, 106: 4, 107: 7, 108: 3, 109: 6, 110: 3,
    111: 5, 112: 4, 113: 5, 114: 6
}

# Surah names in Arabic
SURAH_NAMES = [
    'الفاتحة', 'البقرة', 'آل عمران', 'النساء', 'المائدة', 'الأنعام', 'الأعراف', 'الأنفال', 'التوبة', 'يونس',
    'هود', 'يوسف', 'الرعد', 'إبراهيم', 'الحجر', 'النحل', 'الإسراء', 'الكهف', 'مريم', 'طه',
    'الأنبياء', 'الحج', 'المؤمنون', 'النور', 'الفرقان', 'الشعراء', 'النمل', 'القصص', 'العنكبوت', 'الروم',
    'لقمان', 'السجدة', 'الأحزاب', 'سبأ', 'فاطر', 'يس', 'الصافات', 'ص', 'الزمر', 'غافر',
    'فصلت', 'الشورى', 'الزخرف', 'الدخان', 'الجاثية', 'الأحقاف', 'محمد', 'الفتح', 'الحجرات', 'ق',
    'الذاريات', 'الطور', 'النجم', 'القمر', 'الرحمن', 'الواقعة', 'الحديد', 'المجادلة', 'الحشر', 'الممتحنة',
    'الصف', 'الجمعة', 'المنافقون', 'التغابن', 'الطلاق', 'التحريم', 'الملك', 'القلم', 'الحاقة', 'المعارج',
    'نوح', 'الجن', 'المزمل', 'المدثر', 'القيامة', 'الإنسان', 'المرسلات', 'النبأ', 'النازعات', 'عبس',
    'التكوير', 'الانفطار', 'المطففين', 'الانشقاق', 'البروج', 'الطارق', 'الأعلى', 'الغاشية', 'الفجر', 'البلد',
    'الشمس', 'الليل', 'الضحى', 'الشرح', 'التين', 'العلق', 'القدر', 'البينة', 'الزلزلة', 'العاديات',
    'القارعة', 'التكاثر', 'العصر', 'الهمزة', 'الفيل', 'قريش', 'الماعون', 'الكوثر', 'الكافرون', 'النصر',
    'المسد', 'الإخلاص', 'الفلق', 'الناس'
]

# Reciters mapping
RECITERS_MAP = {
    'الشيخ عبدالباسط عبدالصمد': 'AbdulSamad_64kbps_QuranExplorer.Com',
    'الشيخ عبدالباسط عبدالصمد (مرتل)': 'Abdul_Basit_Murattal_64kbps',
    'الشيخ عبدالرحمن السديس': 'Abdurrahmaan_As-Sudais_64kbps',
    'الشيخ ماهر المعيقلي': 'Maher_AlMuaiqly_64kbps',
    'الشيخ محمد صديق المنشاوي (مجود)': 'Minshawy_Mujawwad_64kbps',
    'الشيخ سعود الشريم': 'Saood_ash-Shuraym_64kbps',
    'الشيخ مشاري العفاسي': 'Alafasy_64kbps',
    'الشيخ محمود خليل الحصري': 'Husary_64kbps',
    'الشيخ عبدالله الحذيفي': 'Hudhaify_64kbps',
    'الشيخ أبو بكر الشاطري': 'Abu_Bakr_Ash-Shaatree_128kbps',
    'الشيخ محمود علي البنا': 'mahmoud_ali_al_banna_32kbps'
}

# Global progress tracking
current_progress = {
    'percent': 0,
    'status': 'جاري التحضير...',
    'log': [],
    'is_running': False,
    'is_complete': False,
    'output_path': None,
    'error': None
}

# Flask App
app = Flask(__name__, static_folder=EXEC_DIR) # Not used directly due to custom route
CORS(app)

def reset_progress():
    global current_progress
    current_progress = {
        'percent': 0,
        'status': 'جاري التحضير...',
        'log': [],
        'is_running': False,
        'is_complete': False,
        'output_path': None,
        'error': None
    }

def add_log(message):
    current_progress['log'].append(message)
    logging.info(f"PROGRESS: {message}")
    print(f'>>> {message}', flush=True)

def update_progress(percent, status):
    current_progress['percent'] = percent
    current_progress['status'] = status
    logging.info(f"STATUS ({percent}%): {status}")

def clear_outputs():
    # Only clear audio directory to keep video history
    if os.path.isdir(AUDIO_DIR):
        try:
            shutil.rmtree(AUDIO_DIR)
            os.makedirs(AUDIO_DIR, exist_ok=True)
        except Exception as e:
            logging.error(f"Error clearing audio output: {e}")
    
def detect_leading_silence(sound, thresh, chunk=10):
    t = 0
    while t < len(sound) and sound[t:t + chunk].dBFS < thresh:
        t += chunk
    return t

def detect_trailing_silence(sound, thresh, chunk=10):
    return detect_leading_silence(sound.reverse(), thresh, chunk)

def download_audio(reciter_id, surah, ayah, idx):
    os.makedirs(AUDIO_DIR, exist_ok=True)
    fn = f'{surah:03d}{ayah:03d}.mp3'
    url = f'https://everyayah.com/data/{reciter_id}/{fn}'
    out = os.path.join(AUDIO_DIR, f'part{idx}.mp3')
    r = http_requests.get(url)
    r.raise_for_status()
    with open(out, 'wb') as f:
        f.write(r.content)
    snd = AudioSegment.from_file(out, 'mp3')
    start = detect_leading_silence(snd, snd.dBFS - 16)
    end = detect_trailing_silence(snd, snd.dBFS - 16)
    trimmed = snd[start:len(snd) - end]
    trimmed.export(out, format='mp3')
    return out

def get_ayah_text(surah, ayah):
    try:
        resp = http_requests.get(f'https://api.alquran.cloud/v1/ayah/{surah}:{ayah}/quran-uthmani')
        resp.raise_for_status()
        return resp.json()['data']['text']
    except Exception as e:
        logging.error(f"Failed to fetch ayah text: {e}")
        raise

def wrap_text(text, per_line):
    """Wrap text into multiple lines based on word count per line"""
    words = text.split()
    lines = [' '.join(words[i:i + per_line]) for i in range(0, len(words), per_line)]
    return '\n'.join(lines)

def create_text_clip(arabic, duration, video_height=1080):
    """
    Create text clip for Arabic only.
    Dynamically adjusts font size and wrapping based on text length to ensure
    it looks organized and fits the screen beautifully.
    """
    words = arabic.split()
    word_count = len(words)
    
    # Dynamic settings based on text length
    if word_count > 60:
        fontsize = 16
        per_line = 10
    elif word_count > 40:
        fontsize = 20
        per_line = 9
    elif word_count > 25:
        fontsize = 25
        per_line = 8
    elif word_count > 15:
        fontsize = 30
        per_line = 7
    else:
        fontsize = 35
        per_line = 6
        
    wrapped_text = wrap_text(arabic, per_line)
    
    # Create the text clip centered on screen
    # Use TextClip with the correct bundled font path
    ar_clip = TextClip(
        wrapped_text, 
        font=FONT_PATH_ARABIC, 
        fontsize=fontsize, 
        color='white', 
        method='caption', 
        size=(900, None), # Allow height to expand as needed, constrain width
        align='center',
    ).set_duration(duration).set_position('center')
    
    return ar_clip


def pick_bg():
    try:
        files = [f for f in os.listdir(VISION_DIR) if f.startswith('nature_part') and f.endswith('.mp4')]
        if not files: 
            logging.error("No bg videos found in vision folder!")
            raise ValueError("No background videos found.")
        return os.path.join(VISION_DIR, random.choice(files))
    except Exception as e:
        logging.error(f"Error picking background: {e}")
        raise

def build_video(reciter_id, surah, start_ayah, end_ayah=None):
    """
    Build video from start_ayah to end_ayah.
    If end_ayah is None, it defaults to start_ayah + 9 or max ayah of surah.
    """
    global current_progress
    try:
        current_progress['is_running'] = True
        current_progress['is_complete'] = False
        current_progress['error'] = None
        
        add_log('[1] Clearing output folders...')
        update_progress(5, 'جاري تنظيف ملفات الإخراج...')
        clear_outputs()
        
        max_ayah = VERSE_COUNTS[surah]
        # Use end_ayah if provided, otherwise default to start_ayah + 9
        if end_ayah is None:
            last_ayah = min(start_ayah + 9, max_ayah)
        else:
            last_ayah = min(end_ayah, max_ayah)
        
        # Ensure last_ayah is not less than start_ayah
        if last_ayah < start_ayah:
            last_ayah = start_ayah
        
        total = last_ayah - start_ayah + 1
        
        add_log(f'[2] Preparing {total} آيات (from {start_ayah} to {last_ayah})')
        update_progress(10, f'جاري تحضير {total} آيات...')
        
        clips = []
        for idx, ayah in enumerate(range(start_ayah, last_ayah + 1), start=1):
            progress_per_ayah = 70 / total
            base_progress = 10 + (idx - 1) * progress_per_ayah
            
            add_log(f'[3.{idx}] Downloading audio for آية {ayah}')
            update_progress(int(base_progress + progress_per_ayah * 0.3), f'جاري تحميل صوت الآية {ayah}...')
            ap = download_audio(reciter_id, surah, ayah, idx - 1)
            
            add_log(f'[3.{idx}] Fetching texts')
            update_progress(int(base_progress + progress_per_ayah * 0.5), f'جاري جلب نص الآية {ayah}...')
            ar = get_ayah_text(surah, ayah)
            
            dur = AudioFileClip(ap).duration
            audio = AudioFileClip(ap).audio_fadein(0.2).audio_fadeout(0.2)
            
            add_log(f'[3.{idx}] Building segment')
            update_progress(int(base_progress + progress_per_ayah * 0.8), f'جاري إنشاء مقطع الآية {ayah}...')
            bg = VideoFileClip(pick_bg())
            seg_bg = bg.fx(vfx.loop, duration=dur).subclip(0, dur)
            ar_clip = create_text_clip(ar, dur)
            
            seg = CompositeVideoClip([seg_bg, ar_clip]).set_audio(audio)
            clips.append(seg)
        
        add_log('[4] Concatenating segments...')
        update_progress(85, 'جاري دمج المقاطع...')
        final = concatenate_videoclips(clips, method='compose')
        
        # Generate a unique filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        surah_name = SURAH_NAMES[surah-1]
        filename = f"QuranReel_{surah_name}_{start_ayah}-{last_ayah}_{timestamp}.mp4"
        out = os.path.join(VIDEO_DIR, filename)
        
        add_log(f'[5] Writing final video → {out}')
        update_progress(90, 'جاري كتابة الفيديو النهائي...')
        final.write_videofile(out, fps=24, codec='libx264', audio_codec='aac', audio_bitrate='192k', verbose=False, ffmpeg_params=['-movflags', '+faststart'])
        
        add_log('[6] Done!')
        update_progress(100, 'تم بنجاح!')
        current_progress['is_complete'] = True
        current_progress['output_path'] = out
        
    except Exception as e:
        logger_error_msg = f"Error in build_video: {str(e)}\n{traceback.format_exc()}"
        logging.error(logger_error_msg)
        current_progress['error'] = str(e)
        add_log(f'[ERROR] {str(e)}')
        update_progress(0, f'خطأ: {str(e)}')
    finally:
        current_progress['is_running'] = False

# API Routes
@app.route('/')
def serve_ui():
    # Use robust path for UI.html
    if os.path.exists(UI_PATH):
        return send_file(UI_PATH)
    else:
        return f"Error: UI.html not found at {UI_PATH}", 404

@app.route('/api/generate', methods=['POST'])
def generate_video():
    global current_progress
    
    if current_progress['is_running']:
        return jsonify({'error': 'عملية إنشاء فيديو قيد التنفيذ بالفعل'}), 400
    
    data = request.json
    reciter_id = data.get('reciter')
    surah = int(data.get('surah', 1))
    start_ayah = int(data.get('startAyah', 1))
    end_ayah = data.get('endAyah')
    if end_ayah is not None:
        end_ayah = int(end_ayah)
    
    reset_progress()
    
    # Start video generation in background thread
    thread = threading.Thread(target=build_video, args=(reciter_id, surah, start_ayah, end_ayah), daemon=True)
    thread.start()
    
    return jsonify({'success': True, 'message': 'بدأ إنشاء الفيديو'})

@app.route('/api/progress', methods=['GET'])
def get_progress():
    return jsonify(current_progress)

@app.route('/api/config', methods=['GET'])
def get_config():
    return jsonify({
        'surahs': SURAH_NAMES,
        'verseCounts': VERSE_COUNTS,
        'reciters': RECITERS_MAP
    })

@app.route('/outputs/<path:filename>')
def serve_output(filename):
    return send_from_directory(OUT_DIR, filename)

@app.route('/final_video.mp4')
def serve_final_video():
    return send_from_directory(EXEC_DIR, 'final_video.mp4')

if __name__ == '__main__':
    logging.info('Server Starting...')
    print('=' * 50)
    print('  One-Click Quran Reels Generator')
    print('  Running in Portable Mode')
    print('=' * 50)
    
    # Open browser automatically
    Comment
    
    # Start Flask server
    # Important: host='127.0.0.1' as requested
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
