import os
# MAC OS FIX: Tell Pygame not to touch the graphical interface
os.environ["SDL_VIDEODRIVER"] = "dummy" 

import sys
import time
import serial
import pygame
import math
import numpy as np
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, 
                               QVBoxLayout, QHBoxLayout, QLabel, QGroupBox)
from PySide6.QtCore import Qt, QThread, Signal, QTimer

class ControllerWorker(QThread):
    status_signal = Signal(bool, bool)
    telemetry_signal = Signal(list)
    coords_signal = Signal(list)
    target_signal = Signal(list, str)

    def __init__(self):
        super().__init__()
        self.is_running = True
        self.PORT = '/dev/cu.usbserial-0001' 
        self.BAUD = 115200
        self.ser = None
        
        # --- ZWOLNIONE, PRECYZYJNE PRĘDKOŚCI ---
        self.speed_linear = 2.0    
        self.speed_angular = 0.02  
        
        self.current_mode = "XYZ"
        self.ui_update_counter = 0 
        self.stat_btn_pressed = False
        
        # Wymiary ramienia (mm)
        self.a1 = 112.5
        self.a2 = 75.0
        self.a3 = 183.0
        self.a4 = 16.0
        self.a5 = 150.0
        self.a6 = 199.5
        
        self.max_reach = self.a2 + self.a3 + self.a5 + self.a6 - 5.0

        # Physical Home Position (Kształt litery L zdefiniowany przez Ciebie)
        self.home_pos = {
            0: 2047, 1: 3147, 3: 1847, 
            4: 2147, 5: 2247, 6: 2047, 7: 2847
        }
        self.pos = self.home_pos.copy()
        
        # ZERO CALIBRATION (Matematyczne Zero absolutne na podstawie L-Shape)
        self.zero_pos = {
            0: 2047,                                  
            1: 3147 - int(90.0 / 0.088),              
            3: 1847,                                  
            4: 2147,                                  
            5: 2247,                                  
            6: 2047,                                  
            7: 2847                                   
        }
        
        _, initial_ee_pose = self.get_kinematics(self.home_pos)
        self.target_pose = list(initial_ee_pose)
        print(f"[INIT] Initial target set to: {self.target_pose}")
        
        # Pamięć ostatniego CELU matematycznego (Rozwiązuje problem "Flipów")
        self.last_t4 = self.raw_to_rad(self.home_pos[4], 4)
        self.last_t5 = self.raw_to_rad(self.home_pos[5], 5)
        self.last_t6 = self.raw_to_rad(self.home_pos[6], 6)
        
        self.pad_state = {
            'connected': False, 
            'lx': 0.0, 'ly': 0.0, 'rx': 0.0, 'ry': 0.0,
            'btn_cross': False, 'btn_circle': False,
            'dpad_up': False, 'dpad_down': False, 'dpad_left': False, 'dpad_right': False,
            'l1': False, 'r1': False, 'l2': 0.0, 'r2': 0.0,
            'btn_triangle': False, 'btn_square': False
        }
        self.is_homing = False

    def raw_to_rad(self, raw_val, servo_id):
        return math.radians((raw_val - self.zero_pos[servo_id]) * 0.088)

    def rad_to_raw(self, rad, servo_id):
        raw = int(self.zero_pos[servo_id] + (math.degrees(rad) / 0.088))
        return np.clip(raw, 0, 4095)

    def dh_matrix(self, a, alpha, d, theta):
        ct, st = math.cos(theta), math.sin(theta)
        ca, sa = math.cos(alpha), math.sin(alpha)
        return [
            [ct, -st*ca,  st*sa, a*ct],
            [st,  ct*ca, -ct*sa, a*st],
            [0,   sa,     ca,    d],
            [0,   0,      0,     1]
        ]

    def mult_matrix(self, m1, m2):
        res = [[0]*4 for _ in range(4)]
        for i in range(4):
            for j in range(4):
                res[i][j] = (m1[i][0]*m2[0][j] + m1[i][1]*m2[1][j] + 
                             m1[i][2]*m2[2][j] + m1[i][3]*m2[3][j])
        return res

    def get_kinematics(self, pos_dict):
        t1 = self.raw_to_rad(pos_dict[0], 0)
        t2 = self.raw_to_rad(pos_dict[1], 1)
        t3 = self.raw_to_rad(pos_dict[3], 3)
        t4 = self.raw_to_rad(pos_dict[4], 4)
        t5 = self.raw_to_rad(pos_dict[5], 5)
        t6 = self.raw_to_rad(pos_dict[6], 6)

        T1 = self.dh_matrix(self.a2, math.pi/2, self.a1, t1)
        T2 = self.dh_matrix(self.a3, 0, 0, t2)
        T3 = self.dh_matrix(self.a4, math.pi/2, 0, t3)
        T4 = self.dh_matrix(0, -math.pi/2, self.a5, t4)
        T5 = self.dh_matrix(0, math.pi/2, 0, t5)
        T6 = self.dh_matrix(0, 0, self.a6, t6)

        T01 = T1
        T02 = self.mult_matrix(T01, T2)
        T03 = self.mult_matrix(T02, T3)
        T04 = self.mult_matrix(T03, T4)
        T05 = self.mult_matrix(T04, T5)
        T06 = self.mult_matrix(T05, T6)

        shoulder = [round(T01[0][3], 1), round(T01[1][3], 1), round(T01[2][3], 1)]
        elbow    = [round(T02[0][3], 1), round(T02[1][3], 1), round(T02[2][3], 1)]
        wrist    = [round(T04[0][3], 1), round(T04[1][3], 1), round(T04[2][3], 1)]
        ee_pos   = [round(T06[0][3], 1), round(T06[1][3], 1), round(T06[2][3], 1)]

        # Sferyczne kąty Eulera (Z-Y-Z)
        cb = np.clip(T06[2][2], -1.0, 1.0)
        pitch = math.acos(cb)
        
        if abs(math.sin(pitch)) > 0.001:
            yaw = math.atan2(T06[1][2], T06[0][2])
            roll = math.atan2(T06[2][1], -T06[2][0])
        else:
            yaw = math.atan2(T06[1][0], T06[0][0])
            roll = 0.0
        
        ee_full_pose = [ee_pos[0], ee_pos[1], ee_pos[2], yaw, pitch, roll]
        return [shoulder, elbow, wrist, ee_pos], ee_full_pose

    def update_ik_analytical(self):
        yaw, pitch, roll = self.target_pose[3], self.target_pose[4], self.target_pose[5]
        
        cy, sy = math.cos(yaw), math.sin(yaw)
        cp, sp = math.cos(pitch), math.sin(pitch)
        cr, sr = math.cos(roll), math.sin(roll)

        # Macierz Rotacji Sferycznej
        R06 = np.array([
            [cy*cp*cr - sy*sr, -cy*cp*sr - sy*cr, cy*sp],
            [sy*cp*cr + cy*sr, -sy*cp*sr + cy*cr, sy*sp],
            [-sp*cr,            sp*sr,            cp]
        ])

        EE_pos = np.array([self.target_pose[0], self.target_pose[1], self.target_pose[2]])
        Z6_axis = R06[:, 2] 
        WC = EE_pos - Z6_axis * self.a6

        t1 = math.atan2(WC[1], WC[0])

        r_plan = math.sqrt(WC[0]**2 + WC[1]**2) - self.a2 
        z_plan = WC[2] - self.a1 
        
        L = math.sqrt(r_plan**2 + z_plan**2) 
        L1 = self.a3 
        L2 = math.sqrt(self.a4**2 + self.a5**2) 
        
        if L > L1 + L2: 
            L = L1 + L2 - 0.001 
            
        cos_q3 = (L**2 - L1**2 - L2**2) / (2 * L1 * L2)
        cos_q3 = np.clip(cos_q3, -1.0, 1.0)
        q3_inner = math.acos(cos_q3)
        
        gamma = math.atan2(self.a4, self.a5) 
        t3 = math.pi/2 - q3_inner - gamma 

        cos_q2 = (L**2 + L1**2 - L2**2) / (2 * L * L1)
        cos_q2 = np.clip(cos_q2, -1.0, 1.0)
        q2_inner = math.acos(cos_q2)
        
        alpha = math.atan2(z_plan, r_plan)
        t2 = alpha + q2_inner 

        T1_mat = self.dh_matrix(self.a2, math.pi/2, self.a1, t1)
        T2_mat = self.dh_matrix(self.a3, 0, 0, t2)
        T3_mat = self.dh_matrix(self.a4, math.pi/2, 0, t3)
        
        T03 = self.mult_matrix(T1_mat, self.mult_matrix(T2_mat, T3_mat))
        R03 = np.array([
            [T03[0][0], T03[0][1], T03[0][2]],
            [T03[1][0], T03[1][1], T03[1][2]],
            [T03[2][0], T03[2][1], T03[2][2]]
        ])
        
        R36 = np.dot(R03.T, R06)
        
        # --- ZABEZPIECZENIE PRZED OSOBLIWOŚCIĄ GIMBAL LOCK ---
        r_val = math.sqrt(R36[0,2]**2 + R36[1,2]**2)
        
        # Zwiększony próg (0.02 to ok. 1.1 stopnia) - stabilizuje nadgarstek!
        if r_val > 0.02:
            t5_A = math.atan2(r_val, R36[2,2])
            t4_A = math.atan2(R36[1,2], R36[0,2])
            t6_A = math.atan2(R36[2,1], -R36[2,0])
            
            t5_B = math.atan2(-r_val, R36[2,2])
            t4_B = math.atan2(-R36[1,2], -R36[0,2])
            t6_B = math.atan2(-R36[2,1], R36[2,0])
            
            def ang_diff(a, b):
                return abs((a - b + math.pi) % (2*math.pi) - math.pi)
            
            # Algorytm patrzy, do czego dążył w poprzedniej klatce, by uniknąć wibracji
            cost_A = ang_diff(t4_A, self.last_t4) + ang_diff(t5_A, self.last_t5) + ang_diff(t6_A, self.last_t6)
            cost_B = ang_diff(t4_B, self.last_t4) + ang_diff(t5_B, self.last_t5) + ang_diff(t6_B, self.last_t6)
            
            if cost_A <= cost_B:
                t4, t5, t6 = t4_A, t5_A, t6_A
            else:
                t4, t5, t6 = t4_B, t5_B, t6_B
        else:
            # Gdy Pitch jest prawie zero (osobliwość), zamrażamy ID 4 i kręcimy tylko ID 6
            t4 = self.last_t4
            
            # Utrzymujemy znak t5, by zapobiec mikro-skokom
            sign = 1.0 if self.last_t5 >= 0 else -1.0
            t5 = math.atan2(r_val * sign, R36[2,2])
            
            # Bezpieczne wyprowadzenie t6 z pominięciem niestabilnego t4
            if R36[2,2] > 0:
                t6 = math.atan2(-R36[0,1], R36[0,0]) - t4
            else:
                t6 = math.atan2(R36[0,1], -R36[0,0]) + t4

        # Zapisujemy do pamięci na następną klatkę
        self.last_t4 = t4
        self.last_t5 = t5
        self.last_t6 = t6

        target_raw = {
            0: self.rad_to_raw(t1, 0),
            1: self.rad_to_raw(t2, 1),
            3: self.rad_to_raw(t3, 3),
            4: self.rad_to_raw(t4, 4),
            5: self.rad_to_raw(t5, 5),
            6: self.rad_to_raw(t6, 6)
        }

        # Złoty środek kagańca
        max_step = 16 
        
        for servo_id in [0, 1, 3, 4, 5, 6]:
            diff = target_raw[servo_id] - self.pos[servo_id]
            step = np.clip(diff, -max_step, max_step)
            self.pos[servo_id] += step

    def update_pad_state(self, state_dict):
        self.pad_state = state_dict

    def run(self):
        print(f"[INFO] Connecting to ESP32 on {self.PORT}...")
        try:
            self.ser = serial.Serial(self.PORT, self.BAUD, timeout=0.1)
            time.sleep(2)
            serial_ok = True
            print("[SUCC] ESP32 Connected successfully")
        except Exception as e:
            print(f"[ERR] Serial Error: {e}")
            serial_ok = False

        while self.is_running:
            self.status_signal.emit(self.pad_state.get('connected', False), serial_ok)
            
            # Odczyt logów z Arduino (w tym komendy stat)
            if self.ser and self.ser.is_open and self.ser.in_waiting > 0:
                try:
                    line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    if line: print(f"[ESP32] {line}")
                except Exception:
                    pass
            
            if self.pad_state.get('connected', False) and not self.is_homing:
                
                # --- COMMAND: TELEMETRY (D-Pad UP) ---
                is_stat_pressed = self.pad_state.get('dpad_up', False)
                if is_stat_pressed and not self.stat_btn_pressed:
                    if self.ser and self.ser.is_open:
                        self.ser.write(b"stat\n")
                        print("\n[INFO] Requesting telemetry from ESP32...")
                self.stat_btn_pressed = is_stat_pressed

                if self.pad_state.get('btn_square', False): self.current_mode = "XYZ"
                if self.pad_state.get('btn_triangle', False): self.current_mode = "ORIENTATION"
                if self.pad_state.get('btn_circle', False): self.current_mode = "DRIVING"
                if self.pad_state.get('btn_cross', False): self.current_mode = "AUTONOMOUS"

                if self.current_mode == "XYZ":
                    self.target_pose[0] -= self.pad_state.get('ly', 0) * self.speed_linear
                    self.target_pose[1] += self.pad_state.get('lx', 0) * self.speed_linear
                    self.target_pose[2] -= self.pad_state.get('ry', 0) * self.speed_linear

                    dist_from_base = math.sqrt(self.target_pose[0]**2 + self.target_pose[1]**2 + self.target_pose[2]**2)
                    if dist_from_base > self.max_reach:
                        scale = self.max_reach / dist_from_base
                        self.target_pose[0] *= scale
                        self.target_pose[1] *= scale
                        self.target_pose[2] *= scale

                elif self.current_mode == "ORIENTATION":
                    # ZMIANA: Yaw (Lewo/Prawo): Przywrócone '+' -> gałka w lewo = chwytak w lewo
                    self.target_pose[3] += self.pad_state.get('lx', 0) * self.speed_angular
                    
                    # Pitch (Góra/Dół): Zostaje '+' -> gałka w górę = chwytak w górę
                    self.target_pose[4] += self.pad_state.get('ly', 0) * self.speed_angular
                    
                    # Roll (Twist): Zostaje '-' -> gałka w prawo = obraca się w prawo
                    self.target_pose[5] -= self.pad_state.get('rx', 0) * self.speed_angular

                grip_speed = 5
                if self.pad_state.get('l2', 0) > 0.05: self.pos[7] -= (self.pad_state.get('l2', 0) * grip_speed)
                if self.pad_state.get('r2', 0) > 0.05: self.pos[7] += (self.pad_state.get('r2', 0) * grip_speed)
                self.pos[7] = max(0, min(4095, self.pos[7]))

            if not self.is_homing and self.current_mode in ["XYZ", "ORIENTATION"]:
                self.update_ik_analytical()

            self.ui_update_counter += 1
            if self.ui_update_counter % 5 == 0: 
                coords, ee_full = self.get_kinematics(self.pos)
                self.coords_signal.emit(coords)
                self.target_signal.emit(self.target_pose, self.current_mode)
                
                current_telemetry = [self.pos[0], self.pos[1], self.pos[3], 
                                     self.pos[4], self.pos[5], self.pos[6], self.pos[7]]
                self.telemetry_signal.emit(current_telemetry)

            # --- SAFE HOMING (D-Pad DOWN) ---
            if self.pad_state.get('connected', False) and self.pad_state.get('dpad_down', False) and not self.is_homing:
                self.is_homing = True
                print("\n[INFO] Initiating smart homing sequence...")
                if self.ser and self.ser.is_open:
                    self.ser.write(b"reset\n")
                time.sleep(1.0) 
                
                _, home_ee_pose = self.get_kinematics(self.home_pos)
                self.target_pose = list(home_ee_pose)
                
                # Zabezpieczenie stanu pamięci podczas homingu
                self.last_t4 = self.raw_to_rad(self.home_pos[4], 4)
                self.last_t5 = self.raw_to_rad(self.home_pos[5], 5)
                self.last_t6 = self.raw_to_rad(self.home_pos[6], 6)
                
                homing_sequence = [0, 1, 3, 4, 5, 6, 7]
                for servo_id in homing_sequence:
                    target = self.home_pos[servo_id]
                    self.pos[servo_id] = target 
                    
                    if self.ser and self.ser.is_open:
                        if servo_id == 1:
                            cmd = f"1,{int(target)}\n2,{4095 - int(target)}\n"
                            self.ser.write(cmd.encode('utf-8'))
                        else:
                            cmd = f"{servo_id},{int(target)}\n"
                            self.ser.write(cmd.encode('utf-8'))
                    time.sleep(0.5) 
                self.is_homing = False
                print("[SUCC] Homing complete.")

            if self.ser and self.ser.is_open and not self.is_homing:
                cmd_batch = (
                    f"0,{int(self.pos[0])}\n"
                    f"1,{int(self.pos[1])}\n"
                    f"2,{4095 - int(self.pos[1])}\n"
                    f"3,{int(self.pos[3])}\n"
                    f"4,{int(self.pos[4])}\n"
                    f"5,{int(self.pos[5])}\n"
                    f"6,{int(self.pos[6])}\n"
                    f"7,{int(self.pos[7])}\n"
                )
                self.ser.write(cmd_batch.encode('utf-8'))

            time.sleep(0.02)

    def stop(self):
        self.is_running = False
        if self.ser and self.ser.is_open: self.ser.close()
        self.wait()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UGV02 - 6DOF Command Center")
        self.setFixedSize(880, 800) 
        self.setStyleSheet("font-size: 14px;")

        pygame.init()
        pygame.joystick.init()
        self.joystick = None
        self.pad_connected = False
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)

        self._build_mode_panel()
        self._build_status_panel()
        self._build_spatial_panel() 
        self._build_telemetry_panel()
        self.main_layout.addStretch()

        self.worker = ControllerWorker()
        self.worker.status_signal.connect(self.update_statuses)
        self.worker.telemetry_signal.connect(self.update_telemetry)
        self.worker.coords_signal.connect(self.update_coords) 
        self.worker.target_signal.connect(self.update_target_ui)
        self.worker.start()

        self.pad_timer = QTimer()
        self.pad_timer.timeout.connect(self.read_gamepad)
        self.pad_timer.start(20)

    def _build_mode_panel(self):
        mode_group = QGroupBox("Active Control Mode")
        mode_layout = QVBoxLayout()
        self.lbl_mode = QLabel("LOADING...")
        self.lbl_mode.setAlignment(Qt.AlignCenter)
        self.lbl_mode.setStyleSheet("font-size: 24px; font-weight: bold; padding: 10px; border-radius: 5px;")
        mode_layout.addWidget(self.lbl_mode)
        mode_group.setLayout(mode_layout)
        self.main_layout.addWidget(mode_group)

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

    def _build_spatial_panel(self):
        spatial_group = QGroupBox("Task Space & IK Target")
        spatial_layout = QVBoxLayout()
        self.coord_labels = {}
        
        self.lbl_target = QLabel("TARGET: X: 0.0 | Y: 0.0 | Z: 0.0 | Yaw: 0.00 | Pitch: 0.00 | Roll: 0.00")
        self.lbl_target.setStyleSheet("font-family: monospace; color: #ff5555; font-weight: bold; background: #222; padding: 5px;")
        spatial_layout.addWidget(self.lbl_target)
        
        points = ["Shoulder", "Elbow", "Wrist", "Gripper (EE)"]
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
        
    def _build_telemetry_panel(self):
        telemetry_group = QGroupBox("Joint Space (Raw Values 0-4095)")
        telemetry_layout = QVBoxLayout()
        self.servo_labels = []
        servo_names = ["Base (0)", "Shoulder L (1)", "Upperarm (3)", 
                       "Forearm (4)", "Wrist Pitch (5)", "Wrist Roll (6)", "Gripper (7)"]
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
                print(f"[SUCC] Gamepad connected: {self.joystick.get_name()}")
            else:
                empty_state = {
                    'connected': False, 
                    'lx': 0.0, 'ly': 0.0, 'rx': 0.0, 'ry': 0.0,
                    'btn_cross': False, 'btn_circle': False, 'btn_square': False, 'btn_triangle': False,
                    'dpad_up': False, 'dpad_down': False, 'dpad_left': False, 'dpad_right': False,
                    'l1': False, 'r1': False, 'l2': 0.0, 'r2': 0.0
                }
                self.worker.update_pad_state(empty_state)
                return

        try:
            def safe_axis(axis_id):
                if self.joystick and axis_id < self.joystick.get_numaxes():
                    return self.joystick.get_axis(axis_id)
                return 0.0
                
            def safe_btn(btn_id):
                if self.joystick and btn_id < self.joystick.get_numbuttons():
                    return self.joystick.get_button(btn_id)
                return False

            dpad_up, dpad_down, dpad_left, dpad_right = False, False, False, False
            if self.joystick.get_numhats() > 0:
                hx, hy = self.joystick.get_hat(0)
                if hy == 1: dpad_up = True
                if hy == -1: dpad_down = True
                if hx == -1: dpad_left = True
                if hx == 1: dpad_right = True
            else:
                dpad_up = safe_btn(11)
                dpad_down = safe_btn(12)
                dpad_left = safe_btn(13)
                dpad_right = safe_btn(14)

            state = {
                'connected': True,
                'lx': self.apply_deadzone(safe_axis(0)), 
                'ly': self.apply_deadzone(safe_axis(1)),
                'rx': self.apply_deadzone(safe_axis(2)),
                'ry': self.apply_deadzone(safe_axis(3)),
                
                'btn_cross': safe_btn(0),
                'btn_circle': safe_btn(1),
                'btn_square': safe_btn(2),
                'btn_triangle': safe_btn(3),
                
                'dpad_up': dpad_up,
                'dpad_down': dpad_down,
                'dpad_left': dpad_left,
                'dpad_right': dpad_right,
                
                'l1': safe_btn(9),
                'r1': safe_btn(10),
                
                'l2': self.normalize_trigger(safe_axis(4)),
                'r2': self.normalize_trigger(safe_axis(5)),
            }
            self.worker.update_pad_state(state)
            
        except Exception as e:
            print(f"[ERR] Connection lost during read: {e}")
            self.pad_connected = False
            self.joystick = None

    def update_statuses(self, pad_ok, serial_ok):
        self.lbl_gamepad.setText("Gamepad: CONNECTED" if pad_ok else "Gamepad: DISCONNECTED")
        self.lbl_gamepad.setStyleSheet(f"color: {'green' if pad_ok else 'red'}; font-weight: bold;")
        self.lbl_robot.setText("ESP32 Serial: ACTIVE" if serial_ok else "ESP32 Serial: WAITING...")
        self.lbl_robot.setStyleSheet(f"color: {'green' if serial_ok else 'orange'}; font-weight: bold;")

    def update_target_ui(self, t, mode):
        colors = {
            "XYZ": ("#204a87", "#729fcf"),         
            "ORIENTATION": ("#8f5902", "#fce94f"), 
            "DRIVING": ("#a40000", "#ef2929"),     
            "AUTONOMOUS": ("#4e9a06", "#8ae234")   
        }
        bg, fg = colors.get(mode, ("#555", "#fff"))
        self.lbl_mode.setText(f"[{mode}]")
        self.lbl_mode.setStyleSheet(f"font-size: 24px; font-weight: bold; padding: 10px; border-radius: 5px; background-color: {bg}; color: {fg};")
        
        self.lbl_target.setText(f"TARGET => X:{t[0]:.0f} | Y:{t[1]:.0f} | Z:{t[2]:.0f} | Yaw:{t[3]:.2f} | Pitch:{t[4]:.2f} | Roll:{t[5]:.2f}")

    def update_coords(self, coords_list):
        points = ["Shoulder", "Elbow", "Wrist", "Gripper (EE)"]
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