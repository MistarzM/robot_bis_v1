import os
os.environ["SDL_VIDEODRIVER"] = "dummy" 

import sys
import time
import serial
import pygame
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, 
                               QVBoxLayout, QHBoxLayout, QLabel, QGroupBox)
from PySide6.QtCore import Qt, QThread, Signal, QTimer

class ControllerWorker(QThread):
    """
    Background Thread: ONLY handles Serial communication, math, and homing.
    No Pygame code allowed here on macOS!
    """
    status_signal = Signal(bool, bool) # Pad Connected, Serial Connected
    telemetry_signal = Signal(list)    # Positions [0, 1, 3, 4, 5, 6, 7]

    def __init__(self):
        super().__init__()
        self.is_running = True
        self.PORT = '/dev/cu.usbserial-0001' 
        self.BAUD = 115200
        self.ser = None
        self.speed_multiplier = 6
        
        self.home_pos = {
            0: 2147, 1: 3547, 3: 1747, 
            4: 2147, 5: 1547, 6: 2047, 7: 2847
        }
        self.pos = self.home_pos.copy()
        
        # State dictionary updated safely by the Main Thread
        self.pad_state = {
            'connected': False, 'rx': 0.0, 'ry': 0.0,
            'btn_cross': False, 'btn_circle': False,
            'dpad_up': False, 'dpad_down': False, 'dpad_left': False, 'dpad_right': False,
            'l1': False, 'r1': False, 'l2': 0.0, 'r2': 0.0,
            'btn_triangle': False, 'btn_square': False
        }
        self.is_homing = False

    def update_pad_state(self, state_dict):
        """Thread-safe injection of gamepad data from the UI."""
        self.pad_state = state_dict

    def send_cmd(self, servo_id, position):
        if self.ser and self.ser.is_open:
            position = max(0, min(4095, int(position)))
            self.ser.write(f"{servo_id},{position}\n".encode('utf-8'))

    def run(self):
        # 1. Initialize Serial
        print(f"[INFO] connecting to esp32 on {self.PORT}...")
        try:
            self.ser = serial.Serial(self.PORT, self.BAUD, timeout=0.1)
            time.sleep(2)
            print("[SUCC] esp32: connected successfully")
            serial_ok = True
        except Exception as e:
            print(f"[EXCT] Serial Error: {e}")
            serial_ok = False

        # 2. Main Hardware Loop (50Hz)
        while self.is_running:
            # Emit statuses to UI
            self.status_signal.emit(self.pad_state['connected'], serial_ok)
            current_telemetry = [self.pos[0], self.pos[1], self.pos[3], 
                                 self.pos[4], self.pos[5], self.pos[6], self.pos[7]]
            self.telemetry_signal.emit(current_telemetry)

            # Read ESP32 Telemetry
            if self.ser and self.ser.in_waiting > 0:
                try:
                    line = self.ser.readline().decode('utf-8').strip()
                    if line: print(f"[ESP32] {line}")
                except: pass

            # Skip movement calculations if pad is off or currently homing
            if not self.pad_state['connected'] or self.is_homing:
                time.sleep(0.02)
                continue

            # --- KINEMATICS & CONTROL LOGIC ---
            self.pos[0] += self.pad_state['rx'] * self.speed_multiplier
            self.pos[1] -= self.pad_state['ry'] * self.speed_multiplier 

            if self.pad_state['btn_cross']: self.pos[3] += self.speed_multiplier
            if self.pad_state['btn_circle']: self.pos[3] -= self.speed_multiplier

            if self.pad_state['dpad_up']: self.pos[5] += self.speed_multiplier
            if self.pad_state['dpad_down']: self.pos[5] -= self.speed_multiplier
            if self.pad_state['dpad_left']: self.pos[4] -= self.speed_multiplier
            if self.pad_state['dpad_right']: self.pos[4] += self.speed_multiplier

            if self.pad_state['l1']: self.pos[6] -= self.speed_multiplier
            if self.pad_state['r1']: self.pos[6] += self.speed_multiplier

            if self.pad_state['l2'] > 0.05: self.pos[7] -= (self.pad_state['l2'] * self.speed_multiplier)
            if self.pad_state['r2'] > 0.05: self.pos[7] += (self.pad_state['r2'] * self.speed_multiplier)

            # --- SPECIAL COMMANDS ---
            if self.pad_state['btn_triangle']:
                self.is_homing = True
                print("\n[INFO] initiating hardware scan and smart homing...")
                self.ser.write(b"reset\n")
                time.sleep(1.0) 

                homing_sequence = [0, 1, 3, 4, 5, 6, 7]
                for servo_id in homing_sequence:
                    target = self.home_pos[servo_id]
                    self.pos[servo_id] = target 
                    if servo_id == 1:
                        self.send_cmd(1, target)
                        self.send_cmd(2, 4095 - target) 
                    else:
                        self.send_cmd(servo_id, target)
                    print(f"[INFO] homing joint id {servo_id}...")
                    time.sleep(0.5) 
                print("[SUCC] homing sequence complete\n")
                time.sleep(0.5)
                self.is_homing = False

            if self.pad_state['btn_square']:
                print("\n[INFO] requesting telemetry from esp32")
                self.ser.write(b"stat\n")
                time.sleep(0.5)

            # Send positions to robot
            self.send_cmd(0, self.pos[0])
            self.send_cmd(1, self.pos[1])
            self.send_cmd(2, 4095 - self.pos[1])
            self.send_cmd(3, self.pos[3])
            self.send_cmd(4, self.pos[4])
            self.send_cmd(5, self.pos[5])
            self.send_cmd(6, self.pos[6])
            self.send_cmd(7, self.pos[7])

            time.sleep(0.02) # 50Hz Loop

    def stop(self):
        self.is_running = False
        if self.ser and self.ser.is_open: self.ser.close()
        self.wait()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UGV02 - Command Center")
        self.setFixedSize(800, 600)
        self.setStyleSheet("font-size: 14px;")

        # --- PYGAME INIT IN MAIN OS THREAD ---
        pygame.init()
        pygame.joystick.init()
        self.joystick = None
        self.pad_connected = False
        
        # UI Setup
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)

        self._build_status_panel()
        self._build_telemetry_panel()
        self.main_layout.addStretch()

        # Start Background Worker
        self.worker = ControllerWorker()
        self.worker.status_signal.connect(self.update_statuses)
        self.worker.telemetry_signal.connect(self.update_telemetry)
        self.worker.start()

        # 50Hz Timer to safely read Pygame in Main Thread
        self.pad_timer = QTimer()
        self.pad_timer.timeout.connect(self.read_gamepad)
        self.pad_timer.start(20)

    # --- UI BUILDING ---
    def _build_status_panel(self):
        status_group = QGroupBox("System Status")
        status_layout = QHBoxLayout()
        self.lbl_gamepad = QLabel("Gamepad: DISCONNECTED")
        self.lbl_gamepad.setStyleSheet("color: red; font-weight: bold;")
        self.lbl_robot = QLabel("ESP32 Serial: CONNECTING...")
        self.lbl_robot.setStyleSheet("color: orange; font-weight: bold;")
        status_layout.addWidget(self.lbl_gamepad)
        status_layout.addWidget(self.lbl_robot)
        status_group.setLayout(status_layout)
        self.main_layout.addWidget(status_group)

    def _build_telemetry_panel(self):
        telemetry_group = QGroupBox("Arm Telemetry (Raw Values 0-4095)")
        telemetry_layout = QVBoxLayout()
        self.servo_labels = []
        servo_names = ["Base (0)", "Shoulder L (1)", "Upperarm (3)", 
                       "Elbow (4)", "Forearm (5)", "Wrist (6)", "Gripper (7)"]
        for name in servo_names:
            row_layout = QHBoxLayout()
            name_label = QLabel(f"{name}:")
            name_label.setFixedWidth(120)
            value_label = QLabel("0")
            value_label.setStyleSheet("font-family: monospace; font-weight: bold;")
            row_layout.addWidget(name_label)
            row_layout.addWidget(value_label)
            row_layout.addStretch()
            telemetry_layout.addLayout(row_layout)
            self.servo_labels.append(value_label)
        telemetry_group.setLayout(telemetry_layout)
        self.main_layout.addWidget(telemetry_group)

    # --- GAMEPAD READING LOGIC (MAIN THREAD) ---
    def apply_deadzone(self, value, deadzone=0.15):
        return 0.0 if abs(value) < deadzone else value

    def normalize_trigger(self, value):
        return (value + 1.0) / 2.0

    def read_gamepad(self):
        """Reads gamepad safely without crashing macOS"""
        pygame.event.pump()
        
        # Handle reconnection
        if not self.pad_connected:
            if pygame.joystick.get_count() > 0:
                self.joystick = pygame.joystick.Joystick(0)
                self.joystick.init()
                self.pad_connected = True
                print(f"[SUCC] gamepad connected: {self.joystick.get_name()}")
            else:
                self.worker.update_pad_state({'connected': False})
                return

        # Extract values and send to worker
        try:
            state = {
                'connected': True,
                'rx': self.apply_deadzone(self.joystick.get_axis(2)),
                'ry': self.apply_deadzone(self.joystick.get_axis(3)),
                'btn_cross': self.joystick.get_button(0),
                'btn_circle': self.joystick.get_button(1),
                'dpad_up': self.joystick.get_button(11),
                'dpad_down': self.joystick.get_button(12),
                'dpad_left': self.joystick.get_button(13),
                'dpad_right': self.joystick.get_button(14),
                'l1': self.joystick.get_button(9),
                'r1': self.joystick.get_button(10),
                'l2': self.normalize_trigger(self.joystick.get_axis(4)),
                'r2': self.normalize_trigger(self.joystick.get_axis(5)),
                'btn_triangle': self.joystick.get_button(3),
                'btn_square': self.joystick.get_button(2)
            }
            self.worker.update_pad_state(state)
        except pygame.error:
            print("[ERR] Gamepad disconnected!")
            self.pad_connected = False
            self.joystick = None

    # --- GUI UPDATES ---
    def update_statuses(self, pad_ok, serial_ok):
        if pad_ok:
            self.lbl_gamepad.setText("Gamepad: CONNECTED")
            self.lbl_gamepad.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.lbl_gamepad.setText("Gamepad: DISCONNECTED")
            self.lbl_gamepad.setStyleSheet("color: red; font-weight: bold;")
            
        if serial_ok:
            self.lbl_robot.setText("ESP32 Serial: ACTIVE")
            self.lbl_robot.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.lbl_robot.setText("ESP32 Serial: WAITING...")
            self.lbl_robot.setStyleSheet("color: orange; font-weight: bold;")

    def update_telemetry(self, positions):
        if len(positions) == len(self.servo_labels):
            for i in range(len(positions)):
                self.servo_labels[i].setText(str(int(positions[i])))

    def closeEvent(self, event):
        print("[INFO] Shutting down worker thread gracefully...")
        self.worker.stop()
        pygame.quit()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
