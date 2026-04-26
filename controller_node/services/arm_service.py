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
        
        # 1. External: Control commands from Laptop
        self.socket = self.context.socket(zmq.REP)
        self.socket.setsockopt(zmq.LINGER, 0)
        self.socket.bind(f"tcp://0.0.0.0:{config.ZMQ_CONTROL_PORT}")
        
        # 2. Local: Broadcast commands to Chassis
        self.pub_context = zmq.Context()
        self.pub_socket = self.pub_context.socket(zmq.PUB)
        self.pub_socket.bind(f"tcp://127.0.0.1:{config.ZMQ_LOCAL_COMMANDS}")

        # 3. Local: Receive telemetry from Chassis
        self.chassis_sub = self.context.socket(zmq.SUB)
        self.chassis_sub.connect(f"tcp://127.0.0.1:{config.ZMQ_LOCAL_TELEMETRY}")
        self.chassis_sub.setsockopt_string(zmq.SUBSCRIBE, "")
        
        # 4. External: Broadcast full robot state to Laptop
        self.feedback_pub = self.context.socket(zmq.PUB)
        self.feedback_pub.bind(f"tcp://0.0.0.0:{config.ZMQ_FEEDBACK_PORT}")
        
        _, initial_pose = self.kinematics.get_kinematics(self.kinematics.pos)
        self.target_pose = list(initial_pose)
        self.current_mode = "XYZ"
        self.is_homing = False
        self.arm_status = "IDLE"
        
        self.sys_logs = []
        self.last_chassis_telemetry = {"voltage": 0.0, "status": "WAITING"}
        self.last_stat_request = time.time()

    def perform_homing(self):
        self.is_homing = True
        self.arm_status = "HOMING"
        self.sys_logs.append("[INFO] Homing sequence started...")
        self.serial.send_reset()
        time.sleep(1.0) 
        
        _, home_ee_pose = self.kinematics.get_kinematics(config.HOME_POS)
        self.target_pose = list(home_ee_pose)
        
        for servo_id in [0, 1, 3, 4, 5, 6, 7]:
            target = config.HOME_POS[servo_id]
            self.kinematics.pos[servo_id] = target 
            if servo_id == 1:
                self.serial.send_command(f"1,{int(target)}\n2,{4095 - int(target)}\n")
            else:
                self.serial.send_command(f"{servo_id},{int(target)}\n")
            time.sleep(0.5) 
            
        self.is_homing = False
        self.arm_status = "IDLE"
        self.sys_logs.append("[SUCC] Homing complete.")

    def process_request(self, msg):
        if msg.get("command") == "CONTROL":
            pad = msg.get("pad", {})
            if pad.get("connected") and not self.is_homing:
                
                if pad.get('btn_square'): self.current_mode = "XYZ"
                if pad.get('btn_triangle'): self.current_mode = "ORIENTATION"
                if pad.get('btn_circle'): self.current_mode = "DRIVING"
                if pad.get('btn_cross'): self.current_mode = "AUTONOMOUS"

                # Broadcast to local components (Chassis)
                self.pub_socket.send_json({"pad": pad, "mode": self.current_mode})

                if self.current_mode == "XYZ":
                    self.arm_status = "MOVING (XYZ)"
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
                    self.arm_status = "MOVING (ORI)"
                    self.target_pose[3] += pad.get('lx', 0) * config.SPEED_ANGULAR
                    self.target_pose[4] += pad.get('ly', 0) * config.SPEED_ANGULAR
                    self.target_pose[5] -= pad.get('rx', 0) * config.SPEED_ANGULAR

                if pad.get('l2', 0) > 0.05: self.kinematics.pos[7] -= (pad.get('l2', 0) * config.GRIP_SPEED)
                if pad.get('r2', 0) > 0.05: self.kinematics.pos[7] += (pad.get('r2', 0) * config.GRIP_SPEED)
                self.kinematics.pos[7] = max(0, min(4095, self.kinematics.pos[7]))

                if pad.get('dpad_down', False):
                    self.perform_homing()
                else:
                    self.kinematics.solve_ik(self.target_pose)

        return {"status": "OK"}

    def broadcast_telemetry(self):
        if time.time() - self.last_stat_request > 1.0:
            self.serial.request_stat()
            self.last_stat_request = time.time()

        coords, _ = self.kinematics.get_kinematics(self.kinematics.pos)
        
        telemetry = {
            "node_status": "ACTIVE",
            "arm_status": self.arm_status,
            "chassis_status": self.last_chassis_telemetry.get("status", "OFFLINE"),
            "camera_status": "ACTIVE",
            "coords": [[float(val) for val in point] for point in coords],
            "target": [float(t) for t in self.target_pose],
            "mode": self.current_mode,
            "servos": [int(self.kinematics.pos[i]) for i in [0, 1, 3, 4, 5, 6, 7]],
            "chassis_data": self.last_chassis_telemetry,
            "logs": self.sys_logs.copy()
        }
        self.feedback_pub.send_json(telemetry)
        self.sys_logs.clear()

    def start(self):
        self.serial.connect()
        print(f"[NET] Control Port {config.ZMQ_CONTROL_PORT}. Feedback Port {config.ZMQ_FEEDBACK_PORT}.")
        
        try:
            while True:
                # 1. Fetch Local Telemetry
                try:
                    self.last_chassis_telemetry = self.chassis_sub.recv_json(flags=zmq.NOBLOCK)
                    self.last_chassis_telemetry["status"] = "ACTIVE"
                except zmq.Again:
                    pass

                # 2. Fetch Serial Logs
                esp_logs = self.serial.read_telemetry()
                if esp_logs:
                    self.sys_logs.extend(esp_logs)

                # 3. Broadcast Global Telemetry
                self.broadcast_telemetry()

                # 4. Process Fast Control Port
                try:
                    msg = self.socket.recv_json(flags=zmq.NOBLOCK)
                    reply = self.process_request(msg)
                    if not self.is_homing:
                        self.serial.send_positions(self.kinematics.pos)
                    self.socket.send_json(reply)
                except zmq.Again:
                    pass
                
                time.sleep(0.01)

        except KeyboardInterrupt:
            pass
        finally:
            self.serial.disconnect()
            self.socket.close()
            self.feedback_pub.close()
            self.context.term()

if __name__ == "__main__":
    server = RobotServer()
    server.start()