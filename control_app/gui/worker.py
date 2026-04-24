# gui/worker.py
import time
import math
from PySide6.QtCore import QThread, Signal
from core import config
from core.kinematics import RobotKinematics
from hardware.gamepad import GamepadController
from hardware.serial_link import Esp32Serial

class ControllerWorker(QThread):
    status_signal = Signal(bool, bool)
    telemetry_signal = Signal(list)
    coords_signal = Signal(list)
    target_signal = Signal(list, str)

    def __init__(self):
        super().__init__()
        self.is_running = True
        self.current_mode = "XYZ"
        self.ui_update_counter = 0 
        self.stat_btn_pressed = False
        self.is_homing = False

        self.kinematics = RobotKinematics()
        self.gamepad = GamepadController()
        self.serial_link = Esp32Serial()

        _, initial_ee_pose = self.kinematics.get_kinematics(self.kinematics.pos)
        self.target_pose = list(initial_ee_pose)

    def run(self):
        self.serial_link.connect()

        while self.is_running:
            pad_state = self.gamepad.read_state()
            self.status_signal.emit(pad_state.get('connected', False), self.serial_link.is_connected)
            
            self.serial_link.read_telemetry()
            
            if pad_state.get('connected', False) and not self.is_homing:
                
                # Tryby
                if pad_state.get('btn_square', False): self.current_mode = "XYZ"
                if pad_state.get('btn_triangle', False): self.current_mode = "ORIENTATION"
                if pad_state.get('btn_circle', False): self.current_mode = "DRIVING"
                if pad_state.get('btn_cross', False): self.current_mode = "AUTONOMOUS"

                # Logika Ruchu
                if self.current_mode == "XYZ":
                    self.target_pose[0] -= pad_state.get('ly', 0) * config.SPEED_LINEAR
                    self.target_pose[1] += pad_state.get('lx', 0) * config.SPEED_LINEAR
                    self.target_pose[2] -= pad_state.get('ry', 0) * config.SPEED_LINEAR

                    dist = math.sqrt(self.target_pose[0]**2 + self.target_pose[1]**2 + self.target_pose[2]**2)
                    if dist > config.MAX_REACH:
                        scale = config.MAX_REACH / dist
                        self.target_pose[0] *= scale
                        self.target_pose[1] *= scale
                        self.target_pose[2] *= scale

                elif self.current_mode == "ORIENTATION":
                    self.target_pose[3] += pad_state.get('lx', 0) * config.SPEED_ANGULAR
                    self.target_pose[4] += pad_state.get('ly', 0) * config.SPEED_ANGULAR
                    self.target_pose[5] -= pad_state.get('rx', 0) * config.SPEED_ANGULAR

                # Gripper
                grip_speed = 5
                if pad_state.get('l2', 0) > 0.05: self.kinematics.pos[7] -= (pad_state.get('l2', 0) * grip_speed)
                if pad_state.get('r2', 0) > 0.05: self.kinematics.pos[7] += (pad_state.get('r2', 0) * grip_speed)
                self.kinematics.pos[7] = max(0, min(4095, self.kinematics.pos[7]))

                # Telemetria z D-Pada
                is_stat_pressed = pad_state.get('dpad_up', False)
                if is_stat_pressed and not self.stat_btn_pressed:
                    self.serial_link.request_stat()
                self.stat_btn_pressed = is_stat_pressed

                # Homing
                if pad_state.get('dpad_down', False):
                    self._perform_homing()
                else:
                    self.kinematics.solve_ik(self.target_pose)

            # Aktualizacja UI
            self.ui_update_counter += 1
            if self.ui_update_counter % 5 == 0: 
                coords, _ = self.kinematics.get_kinematics(self.kinematics.pos)
                self.coords_signal.emit(coords)
                self.target_signal.emit(self.target_pose, self.current_mode)
                
                telem = [self.kinematics.pos[i] for i in [0, 1, 3, 4, 5, 6, 7]]
                self.telemetry_signal.emit(telem)

            if not self.is_homing:
                self.serial_link.send_positions(self.kinematics.pos)

            time.sleep(0.02)

    def _perform_homing(self):
        self.is_homing = True
        print("\n[INFO] Initiating smart homing sequence...")
        self.serial_link.send_reset()
        time.sleep(1.0) 
        
        _, home_ee_pose = self.kinematics.get_kinematics(config.HOME_POS)
        self.target_pose = list(home_ee_pose)
        
        self.kinematics.last_t4 = self.kinematics.raw_to_rad(config.HOME_POS[4], 4)
        self.kinematics.last_t5 = self.kinematics.raw_to_rad(config.HOME_POS[5], 5)
        self.kinematics.last_t6 = self.kinematics.raw_to_rad(config.HOME_POS[6], 6)
        
        for servo_id in [0, 1, 3, 4, 5, 6, 7]:
            target = config.HOME_POS[servo_id]
            self.kinematics.pos[servo_id] = target 
            
            if servo_id == 1:
                self.serial_link.send_command(f"1,{int(target)}\n2,{4095 - int(target)}\n")
            else:
                self.serial_link.send_command(f"{servo_id},{int(target)}\n")
            time.sleep(0.5) 
            
        self.is_homing = False
        print("[SUCC] Homing complete.")

    def stop(self):
        self.is_running = False
        self.serial_link.disconnect()
        self.wait()