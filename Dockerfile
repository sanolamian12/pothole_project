FROM python:3.11-slim-bookworm

# 1. 시스템 종속성 및 RPi 공식 레포지토리 설정
RUN apt-get update && apt-get install -y curl gnupg wget \
    && curl -fsSL https://archive.raspberrypi.org/debian/raspberrypi.gpg.key | gpg --dearmor -o /etc/apt/trusted.gpg.d/raspberrypi.gpg \
    && echo "deb http://archive.raspberrypi.org/debian/ bookworm main" > /etc/apt/sources.list.d/raspi.list

# 빌드 도구, 하드웨어(libcamera), OpenCV 통신 패키지 통합 설치
# libcamera-apps-lite: RPi 카메라 제어를 위한 필수 시스템 라이브러리
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    python3-opencv \
    libopencv-dev \
    libcamera-v4l2 \
    libcamera-apps-lite \
    gstreamer1.0-libcamera \
    gstreamer1.0-plugins-good \
    libgl1-mesa-glx \
    i2c-tools \
    spi-tools \
    libatlas-base-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. 파이썬 패키지 설치 전략
RUN pip install --no-cache-dir "numpy<2"

# PyTorch CPU 전용 공식 빌드 설치 (RPi4 Illegal Instruction 방지)
RUN pip install --no-cache-dir torch==2.1.0 torchvision==0.16.0 --extra-index-url https://download.pytorch.org/whl/cpu

# 하드웨어 제어용 RPi.GPIO 추가 및 필수 라이브러리 설치
RUN pip install --no-cache-dir opencv-python gpiozero RPi.GPIO spidev smbus2 ultralytics

# 3. [추가] YOLOv11n 모델 미리 다운로드 및 이름 변경
# 빌드 단계에서 미리 받아두면 실행 시 에러가 절대 나지 않습니다.
RUN wget https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt -O /app/yolov11n.pt

# 4. [핵심] MI48 열화상 카메라 제조사 라이브러리 로컬 설치
COPY pysenxor-master /app/pysenxor-master
RUN cd /app/pysenxor-master && pip install -e .

# 5. 소스 코드 복사
COPY . .

# 6. 환경 변수 설정
ENV OPENBLAS_CORETYPE=ARMV8
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/usr/lib/python3/dist-packages
ENV GST_PLUGIN_PATH=/usr/lib/aarch64-linux-gnu/gstreamer-1.0
# GPIO 핀 팩토리를 RPi.GPIO로 강제 고정
ENV GPIOZERO_PIN_FACTORY=rpigpio

# 디버깅 모드 유지
