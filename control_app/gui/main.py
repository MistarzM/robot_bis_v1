import os
# KAGANIEC NA MACA: Mówimy Pygame, żeby nie dotykał interfejsu graficznego
os.environ["SDL_VIDEODRIVER"] = "dummy" 

import sys
import time
import serial
import pygame
import math
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, 
                               QVBoxLayout, QHBoxLayout, QLabel, QGroupBox)
from PySide6.QtCore import Qt, QThread, Signal, QTimer

class ControllerWorker(QThread):
    """
    Background Thread: ONLY handles Serial communication, math, and homing.
    """
    status_signal = Signal(bool, bool) # Pad Connected, Serial Connected
    telemetry_signal = Signal(list)    # Positions [0, 1, 3, 4, 5, 6, 7]
    coords_signal = Signal(list)

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
        
        # ROBOT DIMENSIONS (mm) - Wymiary z suwmiarki
        self.a1 = 112.5  # Base height
        self.a2 = 75.0   # Base offset (Przesunięcie w XY)
        self.a3 = 183.0  # Upper arm (Długość głównego ramienia)
        self.a4 = 16.0   # Elbow offset (Uskok łokcia na łączeniu czerwone-zielone)
        self.a5 = 150.0  # Forearm (Przedramię)
        self.a6 = 199.5  # Wrist/Gripper (Długość do punktu chwytu)

    # --- MATEMATYKA KINEMATYKI (DH MATRICES) ---
    def raw_to_rad(self, raw_val, center=2048):
        """Converts servo value (0-4095) to radians. 2048 is assumed absolute 0 degrees."""
        return math.radians((raw_val - center) * 0.088)

    def dh_matrix(self, a, alpha, d, theta):
        """Creates a 4x4 Denavit-Hartenberg transformation matrix."""
        ct = math.cos(theta)
        st = math.sin(theta)
        ca = math.cos(alpha)
        sa = math.sin(alpha)
        
        # Standard DH konwencja
        return [
            [ct, -st*ca,  st*sa, a*ct],
            [st,  ct*ca, -ct*sa, a*st],
            [0,   sa,     ca,    d],
            [0,   0,      0,     1]
        ]

    def mult_matrix(self, m1, m2):
        """Multiplies two 4x4 matrices mathematically perfectly."""
        res = [[0]*4 for _ in range(4)]
        for i in range(4):
            for j in range(4):
                res[i][j] = (m1[i][0]*m2[0][j] + m1[i][1]*m2[1][j] + 
                             m1[i][2]*m2[2][j] + m1[i][3]*m2[3][j])
        return res

    def calculate_fk(self):
        """Calculates Forward Kinematics based on precise DH parameters and Matrix Math."""
        # 1. Konwersja danych z serw na radiany (0-4095 -> Radiany)
        # UWAGA: Jeżeli w pozycji "0" ramię sprzętowo nie jest wyprostowane prosto, 
        # może być konieczne dodanie offsetu, np. t2 = self.raw_to_rad(...) - math.pi/2
        
        t1 = self.raw_to_rad(self.pos[0]) # ID 0: Base Yaw (Obrót bazy)
        t2 = self.raw_to_rad(self.pos[1]) # ID 1: Shoulder Pitch (Bark)
        t3 = self.raw_to_rad(self.pos[3]) # ID 3: Elbow Pitch (Łokieć)
        t4 = self.raw_to_rad(self.pos[4]) # ID 4: Forearm Roll (Obrót przedramieniem)
        t5 = self.raw_to_rad(self.pos[5]) # ID 5: Wrist Pitch (Nadgarstek góra/dół)
        t6 = self.raw_to_rad(self.pos[6]) # ID 6: Wrist Roll (Obrót nadgarstka)

        # 2. Generowanie macierzy DH dla każdego segmentu. Parametry: (a, alpha, d, theta)
        
        # BAZA -> BARK (Wysokość a1, przesunięcie w bok a2, skręt osi o 90 stopni)
        T1 = self.dh_matrix(self.a2, math.pi/2, self.a1, t1)
        
        # BARK -> ŁOKIEĆ (Wzdłuż głównego ramienia o długości a3)
        T2 = self.dh_matrix(self.a3, 0, 0, t2)
        
        # ŁOKIEĆ -> PRZEDRAMIĘ (Uskok a4 na łokciu, zmiana osi obrotu na wzdłużną)
        T3 = self.dh_matrix(self.a4, math.pi/2, 0, t3)
        
        # PRZEDRAMIĘ -> NADGARSTEK (Odległość a5, przejście z osi Roll na Pitch)
        T4 = self.dh_matrix(0, -math.pi/2, self.a5, t4)
        
        # NADGARSTEK (Pitch) -> NADGARSTEK (Roll) (Brak dystansu fizycznego na samym stawie)
        T5 = self.dh_matrix(0, math.pi/2, 0, t5)
        
        # NADGARSTEK (Roll) -> CHWYTAK (Odległość a6 do punktu końcowego - End Effector)
        T6 = self.dh_matrix(0, 0, self.a6, t6)

        # 3. Kaskadowe mnożenie macierzy (Łańcuch kinematyczny)
        T01 = T1
        T02 = self.mult_matrix(T01, T2)
        T03 = self.mult_matrix(T02, T3)
        T04 = self.mult_matrix(T03, T4)
        T05 = self.mult_matrix(T04, T5)
        T06 = self.mult_matrix(T05, T6)

        # 4. Wyciąganie wektorów pozycji (kolumna przesunięć z macierzy homogenicznej)
        # Zgodnie z interfejsem UI potrzebujemy: Shoulder, Elbow, Wrist, End Effector
        shoulder_xyz = [round(T01[0][3], 1), round(T01[1][3], 1), round(T01[2][3], 1)]
        elbow_xyz    = [round(T02[0][3], 1), round(T02[1][3], 1), round(T02[2][3], 1)]
        wrist_xyz    = [round(T04[0][3], 1), round(T04[1][3], 1), round(T04[2][3], 1)]
        ee_xyz       = [round(T06[0][3], 1), round(T06[1][3], 1), round(T06[2][3], 1)]

        return [shoulder_xyz, elbow_xyz, wrist_xyz, ee_xyz]

    # --- KOMUNIKACJA I STEROWANIE ---
    def update_pad_state(self, state_dict):
        self.pad_state = state_dict

    def send_cmd(self, servo_id, position):
        if self.ser and self.ser.is_open:
            position = max(0, min(4095, int(position)))
            self.ser.write(f"{servo_id},{position}\n".encode('utf-8'))

    def run(self):
        print(f"[INFO] connecting to esp32 on {self.PORT}...")
        try:
            self.ser = serial.Serial(self.PORT, self.BAUD, timeout=0.1)
            time.sleep(2)
            print("[SUCC] esp32: connected successfully")
            serial_ok = True
        except Exception as e:
            print(f"[EXCT] Serial Error: {e}")
            serial_ok = False

        while self.is_running:
            self.status_signal.emit(self.pad_state['connected'], serial_ok)
            
            current_telemetry = [self.pos[0], self.pos[1], self.pos[3], 
                                 self.pos[4], self.pos[5], self.pos[6], self.pos[7]]
            self.telemetry_signal.emit(current_telemetry)

            if self.ser and self.ser.in_waiting > 0:
                try:
                    line = self.ser.readline().decode('utf-8').strip()
                    if line: print(f"[ESP32] {line}")
                except: pass

            if not self.pad_state['connected'] or self.is_homing:
                time.sleep(0.02)
                continue

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
            
            # WYSYŁANIE KOORDYNATÓW 3D DO GUI (Poprawione wcięcia)
            coords = self.calculate_fk()
            self.coords_signal.emit(coords)
            
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

            self.send_cmd(0, self.pos[0])
            self.send_cmd(1, self.pos[1])
            self.send_cmd(2, 4095 - self.pos[1])
            self.send_cmd(3, self.pos[3])
            self.send_cmd(4, self.pos[4])
            self.send_cmd(5, self.pos[5])
            self.send_cmd(6, self.pos[6])
            self.send_cmd(7, self.pos[7])

            time.sleep(0.02)

    def stop(self):
        self.is_running = False
        if self.ser and self.ser.is_open: self.ser.close()
        self.wait()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UGV02 - Command Center")
        self.setFixedSize(800, 750) 
        self.setStyleSheet("font-size: 14px;")

        pygame.init()
        pygame.joystick.init()
        self.joystick = None
        self.pad_connected = False
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)

        self._build_status_panel()
        self._build_telemetry_panel()
        self._build_spatial_panel() 
        self.main_layout.addStretch()

        self.worker = ControllerWorker()
        self.worker.status_signal.connect(self.update_statuses)
        self.worker.telemetry_signal.connect(self.update_telemetry)
        self.worker.coords_signal.connect(self.update_coords) 
        self.worker.start()

        self.pad_timer = QTimer()
        self.pad_timer.timeout.connect(self.read_gamepad)
        self.pad_timer.start(20)

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

    def _build_spatial_panel(self):
        spatial_group = QGroupBox("Spatial Positioning (X, Y, Z in mm)")
        spatial_layout = QVBoxLayout()
        self.coord_labels = {}
        
        points = ["Shoulder", "Elbow", "Wrist", "Chwytak (EE)"]
        for point in points:
            row = QHBoxLayout()
            name = QLabel(f"{point}:")
            name.setFixedWidth(100)
            val = QLabel("X: 0.0 | Y: 0.0 | Z: 0.0")
            val.setStyleSheet("font-family: monospace; color: cyan; font-weight: bold;")
            
            row.addWidget(name)
            row.addWidget(val)
            spatial_layout.addLayout(row)
            self.coord_labels[point] = val
            
        spatial_group.setLayout(spatial_layout)
        self.main_layout.addWidget(spatial_group)

    def apply_deadzone(self, value, deadzone=0.15):
        return 0.0 if abs(value) < deadzone else value

    def normalize_trigger(self, value):
        return (value + 1.0) / 2.0

    def read_gamepad(self):
        pygame.event.pump()
        if not self.pad_connected:
            if pygame.joystick.get_count() > 0:
                self.joystick = pygame.joystick.Joystick(0)
                self.joystick.init()
                self.pad_connected = True
                print(f"[SUCC] gamepad connected: {self.joystick.get_name()}")
            else:
                self.worker.update_pad_state({'connected': False})
                return

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

    def update_coords(self, coords_list):
        points = ["Shoulder", "Elbow", "Wrist", "Chwytak (EE)"]
        for i, point in enumerate(points):
            c = coords_list[i]
            self.coord_labels[point].setText(f"X: {c[0]:>6} | Y: {c[1]:>6} | Z: {c[2]:>6}")
            
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