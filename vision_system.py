import cv2
import numpy as np
import time
import threading
import os
import sys

os.environ['GPIOZERO_PIN_FACTORY'] = 'rpigpio'
from ultralytics import YOLO
from senxor.mi48 import MI48
from senxor.interfaces import SPI_Interface, I2C_Interface
from smbus import SMBus
from spidev import SpiDev
from gpiozero import DigitalOutputDevice
from senxor.utils import data_to_frame

# 설정 값
THERMAL_MIN_TEMP = 20.0
THERMAL_MAX_TEMP = 40.0
SAVE_DIR = "/app/data/output"
os.makedirs(SAVE_DIR, exist_ok=True)

class VisionSystem:
    def __init__(self):
        # 1. YOLOv11n 모델 로드
        self.model = YOLO('yolov11n.pt')

        # 2. 열화상 카메라(MI48) 설정
        self.i2c = I2C_Interface(SMBus(1), 0x40)

        spi_dev = SpiDev(0, 0)
        self.spi = SPI_Interface(spi_dev, xfer_size=160)
        self.spi.device.max_speed_hz = 200000
        self.spi.device.mode = 0b00
        self.spi.device.bits_per_word = 8
        self.spi.no_cs = True  # 하드웨어 CS를 쓰지 않고 수동 제어
        self.spi.cshigh = True  # venv에 있던 설정

        self.mi48_cs = DigitalOutputDevice("BCM7", active_high=False, initial_value=False)
        self.mi48_reset = DigitalOutputDevice("BCM23", active_high=False, initial_value=True)

        self.mi48 = MI48([self.i2c, self.spi], data_ready=None)
        self.mi48.set_fps(4.0) # venv와 동일하게 4.0

        if int(self.mi48.fw_version[0]) >= 2:
            self.mi48.enable_filter(f1=False, f2=True, f3=False)

        self.mi48.start(stream=True, with_header=True)

        # 3. RGB 카메라 설정 (GStreamer)
        pipeline = (
            "libcamerasrc ! video/x-raw, width=640, height=480 ! "
            "videoconvert ! video/x-raw, format=BGR ! appsink drop=true sync=false"
        )
        self.cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)

        self.latest_thermal_img = None
        self.running = True

    def thermal_thread(self):
        import cv2
        import numpy as np
        print("🌡️ [Stable Mode] Balancing Image Quality & Connectivity...")

        while self.running:
            try:
                # 1. 센서가 데이터를 준비할 충분한 시간 부여 (0.2 -> 0.1)
                time.sleep(0.2) 
                
                self.mi48_cs.on()
                # 2. CS 활성화 후 안정화 대기 (0.002 -> 0.005)
                time.sleep(0.005) 
                
                result = self.mi48.read()
                
                # CS 비활성화 전 아주 짧은 대기
                time.sleep(0.005)
                self.mi48_cs.off()

                if result is not None:
                    # 데이터 분리 및 3840개 안전 추출
                    data = result[0] if isinstance(result, tuple) else result
                    
                    # 3. CRC 통과 데이터만 처리
                    if len(data) >= 3840:
                        # 형체가 잘 보였던 1120 오프셋 적용
                        offset = 1120
                        valid_raw = data[offset : offset + 3840] if len(data) >= (offset + 3840) else data[:3840]
                        
                        # 48x80 변환 및 타입 캐스팅
                        img = np.array(valid_raw, dtype=np.float32).reshape((48, 80))
                        T_min, T_max = 20.0, 40.0
                        img_clipped = np.clip(img, T_min, T_max)
                        img8u = ((img_clipped - T_min) / (T_max - T_min) * 255).astype(np.uint8)
                        shifted_img = np.roll(img8u, shift=-8, axis=1)
                        self.latest_thermal_img = shifted_img
                else:
                    # CRC 에러 등으로 result가 None일 때는 그냥 다음 루프로 넘어감
                    continue

            except Exception as e:
                # 단순 Bad file descriptor 등은 무시하고 루프 유지
                time.sleep(0.1)

            # 전체 루프 주기 조절
            time.sleep(0.01)

    def run(self):
        if not self.cap.isOpened():
            print("❌ Critical: RGB Camera (GStreamer) failed to open!")
            return
        
        print("✅ RGB Camera Pipeline opened. Waiting for frames...")
        threading.Thread(target=self.thermal_thread, daemon=True).start()
        print("🚀 System Started. Capturing and Processing...")

        # 초기 웜업
        for _ in range(5):
            self.cap.read()
            time.sleep(0.1)

        try:
            while self.cap.isOpened():
                ret, rgb_frame = self.cap.read()
                
                # 디버깅용 로그 (데이터 상태 확인)
                if not ret:
                    if int(time.time() % 5) == 0:
                        print("🟡 Waiting for RGB frame (ret is False)")
                    continue

                if self.latest_thermal_img is None:
                    if int(time.time() % 5) == 0:
                        print("🟡 Waiting for Thermal frame (latest_thermal_img is None)")
                    continue

                # --- 여기서부터 분석 및 저장 ---
                try:
                    ts = int(time.time() * 100)
                    
                    # 1. YOLOv11n 추론
                    results = self.model(rgb_frame, verbose=False)[0]

                    # 2. 결과 저장
                    cv2.imwrite(f"{SAVE_DIR}/{ts}_rgb.jpg", rgb_frame)

                    t_img = self.latest_thermal_img.copy()
                    thermal_color = cv2.applyColorMap(t_img, cv2.COLORMAP_JET)
                    cv2.imwrite(f"{SAVE_DIR}/{ts}_thermal.jpg", thermal_color)

                    # 결과가 있을 때만 txt 저장 (선택 사항)
                    if len(results.boxes) > 0:
                        results.save_txt(f"{SAVE_DIR}/{ts}_labels.txt")

                    print(f"✅ Data Set Saved: {ts}")
                    time.sleep(1)

                except Exception as e:
                    print(f"❌ Processing/Save Error: {e}")
                    time.sleep(1)

        except KeyboardInterrupt:
            print("\nStopping...")
            self.running = False
            self.cap.release()
            self.mi48.stop()

if __name__ == "__main__":
    sys_logic = VisionSystem()
    sys_logic.run()
