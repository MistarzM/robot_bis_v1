import time
import zmq
import math
import re
import socket
from core import config
from core.kinematics import RobotKinematics
from hardware.serial_link import Esp32Serial

class ArmServer:
    def __init__(self):
        self.kinematics = RobotKinematics()
        self.serial = Esp32Serial()
        
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP)
        self.socket.setsockopt(zmq.LINGER, 0)
        self.socket.bind(f"tcp://0.0.0.0:{config.ZMQ_CONTROL_PORT}")
        
        self.pub_context = zmq.Context()
        self.pub_socket = self.pub_context.socket(zmq.PUB)
        self.pub_socket.bind(f"tcp://127.0.0.1:{config.ZMQ_LOCAL_COMMANDS}")

        self.chassis_sub = self.context.socket(zmq.SUB)
        self.chassis_sub.connect(f"tcp://127.0.0.1:{config.ZMQ_LOCAL_TELEMETRY}")
        self.chassis_sub.setsockopt_string(zmq.SUBSCRIBE, "")
        
        self.feedback_pub = self.context.socket(zmq.PUB)
        self.feedback_pub.bind(f"tcp://0.0.0.0:{config.ZMQ_FEEDBACK_PORT}")
        
        _, initial_pose = self.kinematics.get_kinematics(config.ELBOW_DOWN_POS)
        self.target_pose = list(initial_pose)
        self.current_mode = "XYZ"
        self.is_homing = False
        self.arm_status = "IDLE"
        
        self.sys_logs = []
        self.last_chassis_telemetry = {"voltage": 0.0, "status": "OFFLINE"}
        self.last_stat_request = time.time()
        
        self.servo_stats = {id: {'temp': '--', 'volt': '--', 'curr': '--', 'status': 'OK'} for id in [0,1,2,3,4,5,6,7]}

    def _get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80)) 
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "NO NETWORK"

    def _get_physical_positions(self):
        phys_pos = {}
        max_servo = getattr(config, 'MAX_SERVO', 4095)
        
        for s_id in [0, 1, 2, 3, 4, 5, 6, 7]:
            base_val = config.ELBOW_DOWN_POS.get(s_id, 2048)
            virt_pos = self.kinematics.pos.get(s_id, base_val)
            delta = virt_pos - base_val
            
            if s_id in [1, 3]:
                phys_pos[s_id] = base_val - delta
            else:
                phys_pos[s_id] = base_val + delta
                
            if s_id == 1:
                phys_pos[2] = config.ELBOW_DOWN_POS.get(2, 2048) + delta
                
        phys_pos[7] = max(0, min(max_servo, phys_pos.get(7, 2048)))
        return phys_pos

    def perform_homing(self):
        self.is_homing = True
        self.arm_status = "HOMING"
        self.sys_logs.append("[INFO] Homing sequence started...")
        
        for s_id in self.servo_stats:
            self.servo_stats[s_id].update({'temp': '--', 'volt': '--', 'curr': '--', 'status': 'OK'})
            
        self.serial.send_reset()
        time.sleep(2.5) 
        
        _, home_ee_pose = self.kinematics.get_kinematics(config.ELBOW_DOWN_POS)
        self.target_pose = list(home_ee_pose)
        
        for servo_id in [0, 1, 3, 4, 5, 6, 7]:
            target = config.ELBOW_DOWN_POS.get(servo_id, 2048)
            self.kinematics.pos[servo_id] = target 
            
            if servo_id == 1:
                target_2 = config.ELBOW_DOWN_POS.get(2, 2048)
                self.serial.send_command(f"1,{int(target)}\n2,{int(target_2)}\n")
            else:
                self.serial.send_command(f"{servo_id},{int(target)}\n")
            
            time.sleep(0.4) 
            
        self.is_homing = False
        self.arm_status = "ACTIVE"
        self.sys_logs.append("[SUCC] Homing complete.")

    def process_request(self, msg):
        if msg.get("command") == "CONTROL":
            pad = msg.get("pad", {})
            if pad.get("connected") and not self.is_homing:
                
                if pad.get('btn_square'): self.current_mode = "XYZ"
                if pad.get('btn_triangle'): self.current_mode = "RPY"  
                if pad.get('btn_circle'): self.current_mode = "DRIVING"
                if pad.get('btn_cross'): self.current_mode = "AUTONOMOUS"

                self.pub_socket.send_json({"pad": pad, "mode": self.current_mode})

                if self.current_mode in ["XYZ", "RPY"]: 
                    moving = abs(pad.get('lx', 0)) > 0.05 or abs(pad.get('ly', 0)) > 0.05 or abs(pad.get('rx', 0)) > 0.05 or abs(pad.get('ry', 0)) > 0.05
                    self.arm_status = f"MOVING ({self.current_mode})" if moving else "ACTIVE"
                    
                    if self.current_mode == "XYZ":
                        self.target_pose[0] -= pad.get('ly', 0) * config.SPEED_LINEAR
                        self.target_pose[1] += pad.get('lx', 0) * config.SPEED_LINEAR
                        self.target_pose[2] -= pad.get('ry', 0) * config.SPEED_LINEAR
                    else:
                        self.target_pose[3] += pad.get('lx', 0) * config.SPEED_ANGULAR
                        self.target_pose[4] += pad.get('ly', 0) * config.SPEED_ANGULAR
                        self.target_pose[5] -= pad.get('rx', 0) * config.SPEED_ANGULAR

                    dist = math.sqrt(self.target_pose[0]**2 + self.target_pose[1]**2 + self.target_pose[2]**2)
                    if dist > config.MAX_REACH:
                        scale = config.MAX_REACH / dist
                        self.target_pose[0] *= scale; self.target_pose[1] *= scale; self.target_pose[2] *= scale
                else:
                    self.arm_status = "IDLE"

                max_servo = getattr(config, 'MAX_SERVO', 4095)
                if pad.get('l2', 0) > 0.05: self.kinematics.pos[7] -= (pad.get('l2', 0) * config.GRIP_SPEED)
                if pad.get('r2', 0) > 0.05: self.kinematics.pos[7] += (pad.get('r2', 0) * config.GRIP_SPEED)
                self.kinematics.pos[7] = max(0, min(max_servo, self.kinematics.pos[7]))

                if pad.get('dpad_down', False):
                    self.perform_homing()
                elif self.current_mode != "DRIVING":
                    self.kinematics.solve_ik(self.target_pose)

        return {"status": "OK"}

    def broadcast_telemetry(self):
        if time.time() - self.last_stat_request > 1.0:
            self.serial.request_stat()
            self.last_stat_request = time.time()

        coords, _ = self.kinematics.get_kinematics(self.kinematics.pos)
        
        phys_pos = self._get_physical_positions()
        servos_payload = []
        for s_id in [0, 1, 2, 3, 4, 5, 6, 7]:
            pos = int(phys_pos.get(s_id, 2048))
            stat = self.servo_stats[s_id]
            servos_payload.append({
                "id": s_id, "pos": pos, "temp": stat['temp'], 
                "volt": stat['volt'], "curr": stat['curr'], "status": stat['status']
            })
        
        self.feedback_pub.send_json({
            "node_status": "ACTIVE", "arm_status": self.arm_status,
            "chassis_status": self.last_chassis_telemetry.get("status", "OFFLINE"),
            "coords": [[float(v) for v in p] for p in coords], "target": [float(t) for t in self.target_pose],
            "mode": self.current_mode, "servos": servos_payload,
            "chassis_data": self.last_chassis_telemetry, "logs": self.sys_logs.copy()
        })
        self.sys_logs.clear()

    def start(self):
        self.serial.connect()
        print(f"[NET] Control: {config.ZMQ_CONTROL_PORT} | Feedback: {config.ZMQ_FEEDBACK_PORT}")
        
        local_ip = self._get_local_ip()
        print(f"[INFO] Publishing IP to OLED: {local_ip}")
        self.serial.send_ip(local_ip)
        time.sleep(0.5)

        print("[INFO] Executing Auto-Homing on startup...")
        self.perform_homing() 
        
        print("[INFO] Fetching initial telemetry...")
        boot_start = time.time()
        while time.time() - boot_start < 5.0:
            self.serial.request_stat()
            time.sleep(0.5)
            esp_logs = self.serial.read_telemetry()
            has_data = False
            if esp_logs:
                for line in esp_logs:
                    if "Temp:" in line and "Volt:" in line:
                        has_data = True
                        try:
                            id_m = re.search(r'ID (\d+)', line)
                            temp_m = re.search(r'Temp: (\d+)C', line)
                            volt_m = re.search(r'Volt: ([\d\.]+)V', line)
                            curr_m = re.search(r'Current: (\d+)mA', line)
                            if id_m:
                                s_id = int(id_m.group(1))
                                self.servo_stats[s_id].update({
                                    'status': 'OK', 'temp': temp_m.group(1), 
                                    'volt': volt_m.group(1), 'curr': curr_m.group(1)
                                })
                        except: pass
            if has_data:
                print("[INFO] Initial telemetry synchronized! Systems GO.")
                break

        try:
            while True:
                try: 
                    self.last_chassis_telemetry = self.chassis_sub.recv_json(flags=zmq.NOBLOCK)
                except zmq.Again: 
                    pass

                esp_logs = self.serial.read_telemetry()
                if esp_logs:
                    for line in esp_logs:
                        if "NOT FOUND" in line:
                            id_m = re.search(r'ID (\d+)', line)
                            if id_m:
                                s_id = int(id_m.group(1))
                                self.servo_stats[s_id].update({'status': 'ERROR', 'temp': '--', 'volt': '--', 'curr': '--'})
                            self.sys_logs.append(line)
                        elif "Temp:" in line and "Volt:" in line:
                            try:
                                id_m = re.search(r'ID (\d+)', line)
                                temp_m = re.search(r'Temp: (\d+)C', line)
                                volt_m = re.search(r'Volt: ([\d\.]+)V', line)
                                curr_m = re.search(r'Current: (\d+)mA', line)
                                if id_m:
                                    s_id = int(id_m.group(1))
                                    self.servo_stats[s_id].update({
                                        'status': 'OK', 'temp': temp_m.group(1), 
                                        'volt': volt_m.group(1), 'curr': curr_m.group(1)
                                    })
                            except: pass
                        elif "[STAT]" not in line: 
                            self.sys_logs.append(line)

                self.broadcast_telemetry()

                try:
                    msg = self.socket.recv_json(flags=zmq.NOBLOCK)
                    reply = self.process_request(msg)
                    if not self.is_homing and self.current_mode != "DRIVING":
                        self.serial.send_positions(self._get_physical_positions())
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
    server = ArmServer()
    server.start()