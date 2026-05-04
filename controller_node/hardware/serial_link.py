import serial
import time
from core import config

class Esp32Serial:
    def __init__(self):
        self.ser = None
        self.is_connected = False

    def connect(self):
        try:
            self.ser = serial.Serial(config.ARM_PORT, config.ARM_BAUD, timeout=0.1)
            time.sleep(2)
            self.is_connected = True
        except Exception:
            self.is_connected = False

    def read_telemetry(self):
        logs = []
        if self.is_connected and self.ser.in_waiting > 0:
            while self.ser.in_waiting > 0:
                try:
                    line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    if line: 
                        logs.append(f"[ESP32] {line}")
                except Exception:
                    pass
        return logs

    def request_stat(self):
        if self.is_connected:
            self.ser.write(b"stat\n")

    def send_reset(self):
        if self.is_connected:
            self.ser.write(b"reset\n")

    def send_command(self, cmd_string):
        if self.is_connected:
            self.ser.write(cmd_string.encode('utf-8'))

    def send_positions(self, pos_dict):
        if self.is_connected:
            cmd_batch = (
                f"0,{int(pos_dict[0])}\n1,{int(pos_dict[1])}\n"
                f"2,{4095 - int(pos_dict[1])}\n3,{int(pos_dict[3])}\n"
                f"4,{int(pos_dict[4])}\n5,{int(pos_dict[5])}\n"
                f"6,{int(pos_dict[6])}\n7,{int(pos_dict[7])}\n"
            )
            self.ser.write(cmd_batch.encode('utf-8'))

    def send_ip(self, ip_address):
        if self.ser and self.ser.is_open:
            try:
                command = f"ip,{ip_address}\n"
                self.ser.write(command.encode('utf-8'))
            except Exception as e:
                print(f"[SERIAL ERR] Failed to send IP: {e}")

    def disconnect(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.is_connected = False