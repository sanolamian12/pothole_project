import cv2
import numpy as np
import smbus2
import time
import os
import sys

def try_open_camera():
    # 1. 가장 권장되는 libcamerasrc 파이프라인
    # 명시적으로 포맷을 지정하지 않고 GStreamer가 최적을 찾게 유도합니다.
    pipeline = (
        "libcamerasrc ! "
        "video/x-raw, width=640, height=480, framerate=30/1 !"
        "videoconvert ! "
        "video/x-raw, format=BGR ! "
        "appsink drop=true sync=false"
    )

    print(f"🔍 [최종 점검] 파이프라인: {pipeline}")    
    cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)

    if cap.isOpened():
        time.sleep(2)
        ret, frame = cap.read()
        if ret and frame is not None:
            print("✅ [성공] 드디어 카메라 프레임 수신 완료!")
            return cap
    
    # 2. 만약 위 방법이 실패하면, 장치 노드 직접 접근 (최후의 수단)
    print("⚠️  libcamerasrc 실패. v4l2src로 직접 접근 시도...")
    v4l2_pipeline = "v4l2src device=/dev/video0 ! videoconvert ! video/x-raw, format=BGR ! appsink"
    cap = cv2.VideoCapture(v4l2_pipeline, cv2.CAP_GSTREAMER)
    
    return cap if cap.isOpened() else None

def main():
    print(f"OpenCV 버전: {cv2.__version__}")
    print(f"GStreamer 지원 여부: {cv2.getBuildInformation().find('GStreamer') != -1}")

    print("🚀 포트홀 탐지 시스템 하드웨어 점검 시작")
    
    # 1. 열화상 센서 체크 (I2C 0x40)
    try:
        bus = smbus2.SMBus(1)
        bus.read_byte(0x40)
        print("✅ [1/2] 열화상 센서(0x40) 응답 확인")
    except Exception as e:
        print(f"⚠️  [1/2] 열화상 센서 응답 없음 (연결 상태 확인 필요)")

    # 2. 카메라 연결 시도
    cap = try_open_camera()

    if cap is None:
        print("❌ [2/2] 카메라 연결 실패. /dev/video0 장치를 확인하세요.")
        sys.exit(1)
    
    print("✅ [2/2] 스트리밍 테스트 시작 (5장 캡처)")
    
    time.sleep(2) # 카메라 안정화

    for i in range(5):
        # 버퍼 비우기
        for _ in range(5):
            cap.grab()

        ret, frame = cap.read()
        if ret and frame is not None:
            timestamp = time.strftime("%H:%M:%S")
            cv2.putText(frame, f"Pothole Test {i+1} [{timestamp}]", (30, 50), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

            file_name = f'/app/pothole_test_{i+1}.jpg'
            cv2.imwrite(file_name, frame)
            print(f"🖼️  사진 저장 완료 ({i+1}/5): {file_name}")
            time.sleep(1)
        else:
            print(f"❌ [{i+1}/5] 프레임 읽기 실패")

    cap.release()
    print("🏁 모든 테스트 종료")

if __name__ == "__main__":
    main()
