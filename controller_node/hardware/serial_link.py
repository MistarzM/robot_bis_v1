import serial
import time
from core import config


class Esp32Serial:
    def __init__(self):
        self.ser = None
        self.is_connected = False

    # lifecycle
    def connect(self):
        try:
            self.ser = serial.Serial(config.ARM_PORT, config.ARM_BAUD, timeout=0.1)
            time.sleep(2)  
            self.is_connected = True
        except Exception:
            self.is_connected = False

    def disconnect(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.is_connected = False

    # inbound
    def read_telemetry(self):
        """Drain any pending lines from the ESP32, tagged with [ESP32]."""
        logs = []
        if not self.is_connected:
            return logs
        try:
            while self.ser.in_waiting > 0:
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    logs.append(f"[ESP32] {line}")
        except Exception:
            pass
        return logs

    # outbound — low level
    def send_command(self, cmd_string: str):
        """Write a raw command string. Caller is responsible for \\n termination."""
        if self.is_connected:
            try:
                self.ser.write(cmd_string.encode('utf-8'))
            except Exception as e:
                print(f"[SERIAL ERR] Failed to send '{cmd_string.strip()}': {e}")

    # outbound — high level commands
    def request_stat(self):
        if self.is_connected:
            self.ser.write(b"stat\n")

    def send_reset(self):
        if self.is_connected:
            self.ser.write(b"reset\n")

    def send_ip(self, ip_address: str):
        if self.is_connected:
            try:
                self.ser.write(f"ip,{ip_address}\n".encode('utf-8'))
            except Exception as e:
                print(f"[SERIAL ERR] Failed to send IP: {e}")

    def send_positions(self, pos_dict: dict):
        if not self.is_connected:
            return

        cmd_batch = (
            f"0,{int(pos_dict.get(0, 2048))}\n"
            f"1,{int(pos_dict.get(1, 2048))}\n"
            f"2,{int(pos_dict.get(2, 2048))}\n"   # <-- shoulder pair partner of ID 1
            f"3,{int(pos_dict.get(3, 2048))}\n"
            f"4,{int(pos_dict.get(4, 2048))}\n"
            f"5,{int(pos_dict.get(5, 2048))}\n"
            f"6,{int(pos_dict.get(6, 2048))}\n"
            f"7,{int(pos_dict.get(7, 2048))}\n"
        )
        try:
            self.ser.write(cmd_batch.encode('utf-8'))
        except Exception as e:
            print(f"[SERIAL ERR] Failed to send positions batch: {e}")