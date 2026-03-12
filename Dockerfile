FROM python:3.11-slim-bookworm

# 1. Add Raspberry Pi official repository
RUN apt-get update && apt-get install -y curl gnupg \
    && curl -fsSL https://archive.raspberrypi.org/debian/raspberrypi.gpg.key | gpg --dearmor -o /etc/apt/trusted.gpg.d/raspberrypi.gpg \
    && echo "deb http://archive.raspberrypi.org/debian/ bookworm main" > /etc/apt/sources.list.d/raspi.list

# 2. Install RPi specific camera libs and system packages
RUN apt-get update && apt-get install -y \
    python3-opencv \
    python3-pip \
    libcamera-v4l2 \
    libcamera-ipa \
    rpicam-apps-lite \
    i2c-tools \
    ca-certificates \
    gstreamer1.0-libcamera \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 3. Install Python libraries (wrapped in quotes to avoid shell errors)
RUN pip install --no-cache-dir "numpy<2" smbus2 adafruit-circuitpython-mlx90640

# 4. Set Environment Variables for Camera
ENV PYTHONPATH=/usr/lib/python3/dist-packages
ENV GST_PLUGIN_PATH=/usr/lib/aarch64-linux-gnu/gstreamer-1.0
ENV LIBCAMERA_IPA_MODULE_PATH=/usr/lib/aarch64-linux-gnu/libcamera

COPY . .

CMD ["python3", "main.py"]
