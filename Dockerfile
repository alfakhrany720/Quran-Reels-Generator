FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    ffmpeg \
    imagemagick \
    fonts-dejavu \
    fonts-liberation \
    fonts-hosny-amiri \
    fontconfig \
    gcc \
    g++ \
    make \
    curl \
    pkg-config \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    libfreetype6-dev \
    libraqm-dev \
    libfribidi-dev \
    libharfbuzz-dev \
    && rm -rf /var/lib/apt/lists/*

# ImageMagick policy: allow MoviePy to use temporary text files/PDF if needed.
RUN for f in \
        /etc/ImageMagick-6/policy.xml \
        /etc/ImageMagick-7/policy.xml; \
    do \
        if [ -f "$f" ]; then \
            sed -i 's/rights="none" pattern="@\*"/rights="read|write" pattern="@*"/g' "$f"; \
            sed -i 's/rights="none" pattern="PDF"/rights="read|write" pattern="PDF"/g' "$f"; \
        fi; \
    done

# Fail the build instead of producing broken Quran text if the Quran font
# is missing from the image.
RUN test -f /usr/share/fonts/opentype/fonts-hosny-amiri/AmiriQuran.ttf

WORKDIR /app

COPY requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

COPY . /app

RUN mkdir -p \
    /app/outputs \
    /app/outputs/audio \
    /app/outputs/video \
    /app/fonts && \
    fc-cache -f -v

ENV FFMPEG_BINARY=/usr/bin/ffmpeg
ENV IMAGEIO_FFMPEG_EXE=/usr/bin/ffmpeg
ENV IMAGEMAGICK_BINARY=/usr/bin/convert

EXPOSE 5000

CMD ["python", "main.py"]
