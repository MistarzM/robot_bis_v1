import time
import zmq
import math
from core import config
from core.kinematics import RobotKinematics
from hardware.serial_link import Esp32Serial

class RobotServer:
    def __init__(self):
        self.kinematics = RobotKinematics()
        self.serial = Esp32Serial()
        
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP)
        self.socket.setsockopt(zmq.LINGER, 0)
        self.socket.bind(f"tcp://0.0.0.0:{config.ZMQ_CONTROL_PORT}")
        
        # Local PUB socket to broadcast gamepad data to chassis_service
        self.pub_context = zmq.Context()
        self.pub_socket = self.pub_context.socket(zmq.PUB)
        self.pub_socket.bind(f"tcp://127.0.0.1:{config.ZMQ_LOCAL_PORT}")
        
        _, initial_pose = self.kinematics.get_kinematics(self.kinematics.pos)
        self.target_pose = list(initial_pose)
        self.current_mode = "XYZ"
        self.is_homing = False
        self.stat_btn_pressed = False
        
        self.sys_logs = []

    def perform_homing(self):
        self.is_homing = True
        self.sys_logs.append("[INFO] Homing sequence started...")
        self.serial.send_reset()
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
                self.serial.send_command(f"1,{int(target)}\n2,{4095 - int(target)}\n")
            else:
                self.serial.send_command(f"{servo_id},{int(target)}\n")
            time.sleep(0.5) 
            
        self.is_homing = False
        self.sys_logs.append("[SUCC] Homing complete.")

    def process_request(self, msg):
        if msg.get("command") == "CONTROL":
            pad = msg.get("pad", {})
            
            if pad.get("connected") and not self.is_homing:
                
                if pad.get('btn_square'): self.current_mode = "XYZ"
                if pad.get('btn_triangle'): self.current_mode = "ORIENTATION"
                if pad.get('btn_circle'): self.current_mode = "DRIVING"
                if pad.get('btn_cross'): self.current_mode = "AUTONOMOUS"

                # Broadcast gamepad state and mode to local services
                self.pub_socket.send_json({"pad": pad, "mode": self.current_mode})

                if self.current_mode == "XYZ":
                    self.target_pose[0] -= pad.get('ly', 0) * config.SPEED_LINEAR
                    self.target_pose[1] += pad.get('lx', 0) * config.SPEED_LINEAR
                    self.target_pose[2] -= pad.get('ry', 0) * config.SPEED_LINEAR

                    dist = math.sqrt(self.target_pose[0]**2 + self.target_pose[1]**2 + self.target_pose[2]**2)
                    if dist > config.MAX_REACH:
                        scale = config.MAX_REACH / dist
                        self.target_pose[0] *= scale
                        self.target_pose[1] *= scale
                        self.target_pose[2] *= scale

                elif self.current_mode == "ORIENTATION":
                    self.target_pose[3] += pad.get('lx', 0) * config.SPEED_ANGULAR
                    self.target_pose[4] += pad.get('ly', 0) * config.SPEED_ANGULAR
                    self.target_pose[5] -= pad.get('rx', 0) * config.SPEED_ANGULAR

                if pad.get('l2', 0) > 0.05: self.kinematics.pos[7] -= (pad.get('l2', 0) * config.GRIP_SPEED)
                if pad.get('r2', 0) > 0.05: self.kinematics.pos[7] += (pad.get('r2', 0) * config.GRIP_SPEED)
                self.kinematics.pos[7] = max(0, min(4095, self.kinematics.pos[7]))

                is_stat = pad.get('dpad_up', False)
                if is_stat and not self.stat_btn_pressed:
                    self.serial.request_stat()
                    self.sys_logs.append("[INFO] Requested STAT from ESP32...")
                self.stat_btn_pressed = is_stat

                if pad.get('dpad_down', False):
                    self.perform_homing()
                else:
                    self.kinematics.solve_ik(self.target_pose)

        coords, _ = self.kinematics.get_kinematics(self.kinematics.pos)
        
        reply = {
            "status": "OK",
            "coords": [[float(val) for val in point] for point in coords],
            "target": [float(t) for t in self.target_pose],
            "mode": self.current_mode,
            "servos": [int(self.kinematics.pos[i]) for i in [0, 1, 3, 4, 5, 6, 7]],
            "logs": self.sys_logs.copy() 
        }
        self.sys_logs.clear()
        return reply

    def start(self):
        self.serial.connect()
        print(f"[NET] Server is running on port {config.ZMQ_ARM_PORT}. Waiting for laptop...")
        
        try:
            while True:
                msg = self.socket.recv_json()
                
                esp_logs = self.serial.read_telemetry()
                if esp_logs:
                    self.sys_logs.extend(esp_logs)
                
                reply = self.process_request(msg)
                
                if not self.is_homing:
                    self.serial.send_positions(self.kinematics.pos)
                
                self.socket.send_json(reply)

        except KeyboardInterrupt:
            print("\n[INFO] Server stopped manually (Ctrl+C).")
        except Exception as e:
            print(f"\n[CRITICAL] Server crashed with error: {e}")
        finally:
            print("[INFO] Cleaning up network ports and shutting down...")
            self.serial.disconnect()
            self.socket.close()
            self.context.term()
            self.pub_socket.close()
            self.pub_context.term()

if __name__ == "__main__":
    server = RobotServer()
    server.start()