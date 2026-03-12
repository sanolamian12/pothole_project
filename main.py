import cv2
import numpy as np
import smbus2
import time
import sys

def try_open_camera():
    # Use the specific format detected by rpicam-hello (SGBRG10, etc.)
    # videoconvert will handle the conversion to BGR for OpenCV
    pipeline = (
        "libcamerasrc ! "
        "video/x-raw, width=640, height=480 ! "
        "videoconvert ! "
        "video/x-raw, format=BGR ! "
        "appsink drop=true sync=false"
    )

    print(f"🔍 [Check] Connecting to Camera with Pipeline: {pipeline}")
    cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)

    # Wait for the sensor to warm up
    time.sleep(2)

    if cap.isOpened():
        ret, frame = cap.read()
        if ret:
            print("✅ [Success] Camera connection confirmed!")
            return cap
    
    # Final fallback to V4L2 if libcamerasrc fails
    print("⚠️  libcamerasrc failed. Trying direct V4L2...")
    v4l2_pipeline = "v4l2src device=/dev/video0 ! video/x-raw, width=640, height=480 ! videoconvert ! video/x-raw, format=BGR ! appsink"
    cap = cv2.VideoCapture(v4l2_pipeline, cv2.CAP_GSTREAMER)
    return cap if cap.isOpened() else None

def main():
    print("🚀 Initializing Pothole Detection System...")
    
    # 1. Thermal Sensor Check
    try:
        bus = smbus2.SMBus(1)
        bus.read_byte(0x40)
        print("✅ [1/2] Thermal Sensor detected (0x40)")
    except Exception as e:
        print(f"❌ [1/2] Thermal Sensor not found: {e}")

    # 2. RGB Camera Check
    cap = try_open_camera()
    if cap is None:
        print("❌ [2/2] RGB Camera failed to open.")
        sys.exit(1)
    
    print("✅ [2/2] RGB Camera active. Capturing 5 frames...")

    for i in range(5):
        # Flush old frames in buffer
        for _ in range(5):
            cap.grab()
            
        ret, frame = cap.read()
        if ret:
            file_name = f"/app/pothole_test_{i+1}.jpg"
            cv2.imwrite(file_name, frame)
            print(f"🖼️  Saved: {file_name}")
            time.sleep(1)
        else:
            print(f"❌ Failed to capture frame {i+1}")

    cap.release()
    print("🏁 Hardware Test Complete.")

if __name__ == "__main__":
    main()
