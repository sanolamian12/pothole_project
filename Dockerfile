FROM python:3.11-slim-bookworm

# libcamera-apps-lite를 설치하여 필요한 GStreamer 플러그인을 가져옵니다.
RUN apt-get update && apt-get install -y \
#    python3-opencv \
    libgl1 \
    libglib2.0-0 \
#    libcamera-dev \
#    libcamera0.0.3 \
    libcamera-v4l2 \
    libcamera-ipa \
#    libcamera-apps-lite \
    gstreamer1.0-libcamera \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# GStreamer 플러그인 경로 강제 지정
ENV GST_PLUGIN_PATH=/usr/lib/aarch64-linux-gnu/gstreamer-1.0
ENV LD_LIBRARY_PATH=/usr/lib/aarch64-linux-gnu
# ... (기존 내용 아래에 추가)
# 호스트의 라이브러리 경로를 Python이 기본으로 뒤지는 경로에 포함시킵니다.
#ENV LD_LIBRARY_PATH=/usr/local/lib:/usr/lib/aarch64-linux-gnu:$LD_LIBRARY_PATH

CMD ["python", "main.py"]


#FROM python:3.11-slim-bookworm
# 1. 시스템 의존성 설치 (GStreamer 및 libcamera 관련 필수 패키지)
#RUN apt-get update && apt-get install -y \
#    libopencv-dev \
#    python3-opencv \
#    libcamera-dev \
#    libcamera-v4l2 \
#    gstreamer1.0-tools \
#    gstreamer1.0-plugins-base \
#    gstreamer1.0-plugins-good \
#    gstreamer1.0-plugins-bad \
#    gstreamer1.0-libcamera \
#    v4l-utils \
#    && rm -rf /var/lib/apt/lists/*

#WORKDIR /app

# 2. Python 라이브러리 설치
#COPY requirements.txt .
# 주의: requirements.txt에 opencv-python이 있다면 삭제하거나 
# 아래와 같이 시스템 OpenCV를 사용하도록 설정하는 것이 좋습니다.
#RUN pip install --no-cache-dir -r requirements.txt

#COPY . .

# 3. GStreamer가 libcamera를 찾을 수 있도록 경로 설정 (중요)
#ENV GST_PLUGIN_PATH=/usr/lib/aarch64-linux-gnu/gstreamer-1.0

#CMD ["python", "main.py"]
