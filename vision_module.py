import cv2
import numpy as np
import time
import threading
import os
import sys
import json

os.environ['GPIOZERO_PIN_FACTORY'] = 'rpigpio'
from ultralytics import YOLO
from senxor.mi48 import MI48
from senxor.interfaces import SPI_Interface, I2C_Interface
from smbus import SMBus
from spidev import SpiDev
from gpiozero import DigitalOutputDevice
from senxor.utils import data_to_frame  # 임포트 추가

# --- [경로 및 설정값] ---
THERMAL_MIN_TEMP = 20.0
THERMAL_MAX_TEMP = 40.0
# 도커 내부에서 접근하기 용이한 경로 (호스트의 pothole_project/data와 연결)
BASE_DATA_DIR = "/app/data"
UPLOAD_DIR = os.path.join(BASE_DATA_DIR, "upload_queue")

os.makedirs(UPLOAD_DIR, exist_ok=True)

class VisionSystem:
    def __init__(self):
        self.running = True
        self.is_active = True
        self.remote_force_send = 0  # 외부 제어용 플래그
        
        self.latest_thermal_img = None
        self.latest_rgb_frame = None
        self.latest_yolo_data = []

        # 1. YOLOv11n 모델 로드
        self.model = YOLO('yolov11n.pt')

        # 2. 열화상 카메라(MI48) 하드웨어 설정 (기존 안정 버전 복구)
        self.i2c = I2C_Interface(SMBus(1), 0x40)

        spi_dev = SpiDev(0, 0)
        self.spi = SPI_Interface(spi_dev, xfer_size=160)
        self.spi.device.max_speed_hz = 200000
        self.spi.device.mode = 0b00
        self.spi.device.bits_per_word = 8
        self.spi.no_cs = True
        self.spi.cshigh = True

        # CS(BCM7) 및 RESET(BCM23) 제어
        self.mi48_cs = DigitalOutputDevice("BCM7", active_high=False, initial_value=False)
        self.mi48_reset = DigitalOutputDevice("BCM23", active_high=False, initial_value=True)

        self.mi48 = MI48([self.i2c, self.spi], data_ready=None)
        self.mi48.set_fps(4.0)

        if int(self.mi48.fw_version[0]) >= 2:
            self.mi48.enable_filter(f1=False, f2=True, f3=False)

        self.mi48.start(stream=True, with_header=True)

        # 3. RGB 카메라 설정 (GStreamer)
        pipeline = (
            "libcamerasrc ! video/x-raw, width=640, height=480 ! "
            "videoconvert ! video/x-raw, format=BGR ! appsink drop=true sync=false"
        )
        self.cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)

    def thermal_thread(self):
        print("🌡️ [Stable Mode] Thermal Thread Started...")
        while self.running:
            try:
                # 센서 데이터 준비 대기 (안정 버전 0.2s 유지)
                time.sleep(0.2)

                self.mi48_cs.on()
                time.sleep(0.005)
                result = self.mi48.read()
                time.sleep(0.005)
                self.mi48_cs.off()

                if result is not None:
                    data = result[0] if isinstance(result, tuple) else result
                    if len(data) >= 3840:
                        offset = 1120
                        valid_raw = data[offset : offset + 3840] if len(data) >= (offset + 3840) else data[:3840]

                        # 48x80 변환 및 처리
                        img = np.array(valid_raw, dtype=np.float32).reshape((48, 80))
                        img_clipped = np.clip(img, THERMAL_MIN_TEMP, THERMAL_MAX_TEMP)
                        img8u = ((img_clipped - THERMAL_MIN_TEMP) / (THERMAL_MAX_TEMP - THERMAL_MIN_TEMP) * 255).astype(np.uint8)
                        
                        # 순환 이동 적용 및 저장
                        #shifted_img = np.roll(img8u, shift=-8, axis=1)
                        self.latest_thermal_img = img8u
                        
                        # [실시간 덮어쓰기]
                        cv2.imwrite(f"{BASE_DATA_DIR}/live_thermal.jpg", shifted_img)
                
            except Exception as e:
                time.sleep(0.1)
            time.sleep(0.01)

    def check_trigger_conditions(self):
        """트리거 여부를 판단하는 함수"""
        # 1. 외부 강제 전송 플래그
        if self.remote_force_send == 1:
            return True
        # 2. YOLO 객체 감지 시
        if self.latest_yolo_data:
            return True
        # 3. 온도 조건 (열화상 최대값이 설정치의 90% 상회 시)
        if self.latest_thermal_img is not None:
            if np.max(self.latest_thermal_img) > 230:
                return True
        return False

    def save_snapshot(self, rgb_frame, thermal_img, yolo_data):
        """이벤트 발생 시 스냅샷 세트 저장"""
        ts = int(time.time() * 100)
        # RGB 저장
        cv2.imwrite(f"{UPLOAD_DIR}/{ts}_rgb.jpg", rgb_frame)
        # Thermal 저장 (컬러맵 입힘)
        thermal_color = cv2.applyColorMap(thermal_img, cv2.COLORMAP_JET)
        cv2.imwrite(f"{UPLOAD_DIR}/{ts}_thermal.jpg", thermal_color)
        # YOLO 결과 JSON 저장
        with open(f"{UPLOAD_DIR}/{ts}_yolo.json", "w") as f:
            json.dump(yolo_data, f)
        
        print(f"✅ [Snapshot] Trigger Event Saved: {ts}")

    def run(self):
        if not self.cap.isOpened():
            print("❌ RGB Camera Error")
            return

        threading.Thread(target=self.thermal_thread, daemon=True).start()
        print("🚀 Monitoring system started...")

        try:
            while self.cap.isOpened() and self.running:
                ret, rgb_frame = self.cap.read()
                if not ret: continue

                self.latest_rgb_frame = rgb_frame
                # [실시간 덮어쓰기: RGB]
                cv2.imwrite(f"{BASE_DATA_DIR}/live_rgb.jpg", rgb_frame)

                # 1. YOLO 추론
                results = self.model(rgb_frame, verbose=False)[0]
                
                # YOLO 결과 가공
                current_detections = []
                for box in results.boxes:
                    current_detections.append({
                        "box": box.xyxy[0].tolist(),
                        "conf": float(box.conf[0]),
                        "cls": int(box.cls[0])
                    })
                self.latest_yolo_data = current_detections
                
                # [실시간 덮어쓰기: YOLO]
                with open(f"{BASE_DATA_DIR}/live_yolo.json", "w") as f:
                    json.dump(current_detections, f)

                # 2. 트리거 조건 확인
                if self.check_trigger_conditions():
                    if self.latest_thermal_img is not None:
                        self.save_snapshot(rgb_frame, self.latest_thermal_img, current_detections)
                        # 강제 전송 후 플래그 초기화 및 중복 방지 쿨타임
                        if self.remote_force_send == 1: self.remote_force_send = 0
                        time.sleep(2)

        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        print("\nStopping...")
        self.running = False
        self.cap.release()
        self.mi48.stop()

if __name__ == "__main__":
    sys_logic = VisionSystem()
    sys_logic.run()
