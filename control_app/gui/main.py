import sys
import time
import serial
import pygame
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, 
                               QVBoxLayout, QHBoxLayout, QLabel, QGroupBox)
from PySide6.QtCore import Qt, QThread, Signal

class ControllerWorker(QThread):
    """
    Background thread running the Pygame controller and ESP32 Serial communication.
    """
    status_signal = Signal(bool)       # Gamepad status (True/False)
    telemetry_signal = Signal(list)    # Positions [0, 1, 3, 4, 5, 6, 7]

    def __init__(self):
        super().__init__()
        self.is_running = True
        
        # hardware config
        self.PORT = '/dev/cu.usbserial-0001' 
        self.BAUD = 115200
        
        # home positions
        self.home_pos = {
            0: 2147, # base
            1: 3547, # shoulder l (shoulder r [2] is mirrored)
            3: 1747, # upperarm
            4: 2147, # elbow
            5: 1547, # forearm 
            6: 2047, # wrist
            7: 2847, # gripper
        }
        self.pos = self.home_pos.copy()
        
        self.ser = None
        self.joystick = None
        self.speed_multiplier = 6

    # --- HELPER METHODS ---
    def send_cmd(self, servo_id, position):
        """sends movement command to esp32 via serial"""
        if self.ser and self.ser.is_open:
            position = max(0, min(4095, int(position)))
            self.ser.write(f"{servo_id},{position}\n".encode('utf-8'))

    def apply_deadzone(self, value, deadzone=0.15):
        """ignores small analog stick drifts"""
        if abs(value) < deadzone:
            return 0.0
        return value

    def normalize_trigger(self, value):
        """converts ps5 trigger range from [-1.0, 1.0] to [0.0, 1.0]"""
        return (value + 1.0) / 2.0

    # --- MAIN THREAD LOOP ---
    def run(self):
        """Initializes hardware and runs the main 50Hz control loop."""
        
        # 1. Initialize Serial
        print(f"[INFO] connecting to esp32 on {self.PORT}...")
        try:
            self.ser = serial.Serial(self.PORT, self.BAUD, timeout=0.1)
            time.sleep(2) # Wait for ESP32 to reboot after serial connection
            print("[SUCC] esp32: connected successfully")
        except Exception as e:
            print(f"[EXCT] Serial Error: {e}")

        # 2. Initialize Pygame & Gamepad
        pygame.init()
        pygame.joystick.init()

        pad_connected = False
        if pygame.joystick.get_count() > 0:
            self.joystick = pygame.joystick.Joystick(0)
            self.joystick.init()
            pad_connected = True
            print(f"[SUCC] gamepad connected: {self.joystick.get_name()}")
        else:
            print("[ERR] no gamepad detected - connect ps5 dualsense")

        clock = pygame.time.Clock()
        print("[SUCC] background controller system ready")

        # 3. Main Loop (Runs continuously in background)
        while self.is_running:
            # Emit status to UI
            self.status_signal.emit(pad_connected)
            
            # Extract current positions for UI update
            current_telemetry = [
                self.pos[0], self.pos[1], self.pos[3], 
                self.pos[4], self.pos[5], self.pos[6], self.pos[7]
            ]
            self.telemetry_signal.emit(current_telemetry)

            if not pad_connected:
                pygame.joystick.quit()
                pygame.joystick.init()
                if pygame.joystick.get_count() > 0:
                    self.joystick = pygame.joystick.Joystick(0)
                    self.joystick.init()
                    pad_connected = True
                time.sleep(1)
                continue

            pygame.event.pump()

            # --- SERIAL READ (ESP32 Telemetry) ---
            if self.ser and self.ser.in_waiting > 0:
                try:
                    line = self.ser.readline().decode('utf-8').strip()
                    if line:
                        print(f"[ESP32] {line}")
                except:
                    pass

            # --- GAMEPAD LOGIC ---
            # Right stick - base and shoulder
            axis_rx = self.apply_deadzone(self.joystick.get_axis(2))
            axis_ry = self.apply_deadzone(self.joystick.get_axis(3))
            
            self.pos[0] += axis_rx * self.speed_multiplier
            self.pos[1] -= axis_ry * self.speed_multiplier 

            # Cross (0) / Circle (1) -> upperarm (id 3)
            if self.joystick.get_button(0): self.pos[3] += self.speed_multiplier
            if self.joystick.get_button(1): self.pos[3] -= self.speed_multiplier

            # D-pad -> elbow (id 4) & forearm (id 5)
            if self.joystick.get_button(11): self.pos[5] += self.speed_multiplier # up
            if self.joystick.get_button(12): self.pos[5] -= self.speed_multiplier # down
            if self.joystick.get_button(13): self.pos[4] -= self.speed_multiplier # left
            if self.joystick.get_button(14): self.pos[4] += self.speed_multiplier # right

            # Bumpers L1 (9) / R1 (10) -> wrist (id 6)
            if self.joystick.get_button(9): self.pos[6] -= self.speed_multiplier
            if self.joystick.get_button(10): self.pos[6] += self.speed_multiplier

            # Triggers L2 (4) / R2 (5) -> gripper (id 7)
            trigger_l2 = self.normalize_trigger(self.joystick.get_axis(4))
            trigger_r2 = self.normalize_trigger(self.joystick.get_axis(5))
            
            if trigger_l2 > 0.05: self.pos[7] -= (trigger_l2 * self.speed_multiplier)
            if trigger_r2 > 0.05: self.pos[7] += (trigger_r2 * self.speed_multiplier)

            # --- SPECIAL COMMANDS ---
            # Triangle (3) -> smart homing sequence
            if self.joystick.get_button(3):
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

            # Square (2) -> stat / telemetry
            if self.joystick.get_button(2):
                print("\n[INFO] requesting telemetry from esp32")
                self.ser.write(b"stat\n")
                time.sleep(0.5)

            # --- SEND MOVEMENT COMMANDS ---
            self.send_cmd(0, self.pos[0])
            self.send_cmd(1, self.pos[1])
            self.send_cmd(2, 4095 - self.pos[1]) # Mirrored shoulder
            self.send_cmd(3, self.pos[3])
            self.send_cmd(4, self.pos[4])
            self.send_cmd(5, self.pos[5])
            self.send_cmd(6, self.pos[6])
            self.send_cmd(7, self.pos[7])

            # Maintain 50Hz loop rate
            clock.tick(50)

    def stop(self):
        """Safely stops the thread and closes ports."""
        self.is_running = False
        if self.ser and self.ser.is_open:
            self.ser.close()
        pygame.quit()
        self.wait()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("UGV02 - Command Center")
        self.setFixedSize(800, 600)
        self.setStyleSheet("font-size: 14px;")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)

        self._build_status_panel()
        self._build_telemetry_panel()
        self.main_layout.addStretch()

        # Initialize and start Worker
        self.worker = ControllerWorker()
        self.worker.status_signal.connect(self.update_gamepad_status)
        self.worker.telemetry_signal.connect(self.update_telemetry)
        self.worker.start()

    def _build_status_panel(self):
        status_group = QGroupBox("System Status")
        status_layout = QHBoxLayout()

        self.lbl_gamepad = QLabel("Gamepad: WAITING...")
        self.lbl_gamepad.setStyleSheet("color: orange; font-weight: bold;")
        
        self.lbl_robot = QLabel(f"ESP32 Serial: CONNECTING...")
        self.lbl_robot.setStyleSheet("color: orange; font-weight: bold;")

        status_layout.addWidget(self.lbl_gamepad)
        status_layout.addWidget(self.lbl_robot)
        status_group.setLayout(status_layout)
        self.main_layout.addWidget(status_group)

    def _build_telemetry_panel(self):
        telemetry_group = QGroupBox("Arm Telemetry (Raw Values 0-4095)")
        telemetry_layout = QVBoxLayout()
        self.servo_labels = []
        
        # Updated to match exactly your 7 active tracking variables
        servo_names = [
            "Base (0)", "Shoulder L (1)", "Upperarm (3)", 
            "Elbow (4)", "Forearm (5)", "Wrist (6)", "Gripper (7)"
        ]
        
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

    def update_gamepad_status(self, is_connected):
        if is_connected:
            self.lbl_gamepad.setText("Gamepad: CONNECTED")
            self.lbl_gamepad.setStyleSheet("color: green; font-weight: bold;")
            self.lbl_robot.setText("ESP32 Serial: ACTIVE")
            self.lbl_robot.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.lbl_gamepad.setText("Gamepad: DISCONNECTED")
            self.lbl_gamepad.setStyleSheet("color: red; font-weight: bold;")

    def update_telemetry(self, positions):
        if len(positions) == len(self.servo_labels):
            for i in range(len(positions)):
                self.servo_labels[i].setText(str(int(positions[i])))

    def closeEvent(self, event):
        print("[INFO] Shutting down worker thread gracefully...")
        self.worker.stop()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
