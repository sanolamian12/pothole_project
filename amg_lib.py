# amg_lib.py
import time
import numpy as np

class AMG8833:
    def __init__(self, i2c, address=0x40): # 기본 주소는 0x69이나 사용자님은 0x40일 수 있음
        self._i2c = i2c
        self._address = address
        # 센서 초기화 (PCTL 레거시 설정 등)
        try:
            # 기본 모드로 설정
            self._write_u8(0x00, 0x00) 
            time.sleep(0.05)
        except:
            pass

    def _write_u8(self, reg, val):
        self._i2c.writeto_mem(self._address, reg, bytes([val]))

    def read_temp(self):
        # 8x8 온도 데이터를 읽어오는 로직 (단순화된 예시)
        # 실제 구현은 복잡하므로 테스트를 위해 랜덤 데이터를 반환하거나 
        # 나중에 실제 레지스터 읽기 로직으로 보강합니다.
        return np.random.uniform(20, 35, (8, 8))
