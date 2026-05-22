import serial
import zmq
import json
import time
from core import config

def start_chassis():
    context = zmq.Context()
    
    sub_socket = context.socket(zmq.SUB)
    sub_socket.connect(f"tcp://127.0.0.1:{config.ZMQ_LOCAL_COMMANDS}")
    sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")

    pub_socket = context.socket(zmq.PUB)
    pub_socket.bind(f"tcp://127.0.0.1:{config.ZMQ_LOCAL_TELEMETRY}")

    print(f"[CHASSIS] Connecting to UGV02 on {config.CHASSIS_PORT}...")
    try:
        chassis = serial.Serial(config.CHASSIS_PORT, config.CHASSIS_BAUD, timeout=0.01)
        time.sleep(2)
        chassis.write((json.dumps({"T": 605, "cmd": 2}) + "\n").encode())
        print("[CHASSIS] Connected and continuous telemetry enabled.")
    except Exception as e:
        print(f"[CHASSIS ERROR] {e}")
        return

    was_moving = False
    current_status = "IDLE"
    last_v = 0.0
    last_telem_send = 0

    current_x = 0.0
    current_z = 0.0
    
    accel_step = getattr(config, 'CHASSIS_ACCEL_STEP', 0.01)
    decel_step = getattr(config, 'CHASSIS_DECEL_STEP', 0.05)

    def smooth_step(current, target):
        """Intelligently applies slow acceleration or fast deceleration"""
        if current < target:
            step = decel_step if current < 0 else accel_step
            return min(current + step, target)
        elif current > target:
            step = decel_step if current > 0 else accel_step
            return max(current - step, target)
        return current

    try:
        while True:
            # 1. Read telemetry from chassis
            if chassis.in_waiting > 0:
                line = chassis.readline().decode('utf-8', errors='ignore').strip()
                if line.startswith('{'): 
                    try:
                        data = json.loads(line)
                        raw_v = data.get("V", data.get("v", 0.0))
                        last_v = raw_v / 100.0  
                    except: 
                        pass
                elif line:
                    print(f"[CHASSIS RAW] {line}")

            # 2. Listen for drive commands
            try:
                msg = sub_socket.recv_json(flags=zmq.NOBLOCK)
                pad = msg.get("pad", {})
                mode = msg.get("mode", "")

                if mode == "DRIVING" and pad.get("connected"):
                    target_x = -pad.get("ly", 0.0) * config.CHASSIS_MAX_SPEED
                    
                    if target_x < -0.01:
                        target_z = pad.get("lx", 0.0) * config.CHASSIS_MAX_SPEED
                    else:
                        target_z = -pad.get("lx", 0.0) * config.CHASSIS_MAX_SPEED
                else:
                    target_x = 0.0
                    target_z = 0.0

                # Process smooth step
                current_x = smooth_step(current_x, target_x)
                current_z = smooth_step(current_z, target_z)

                if abs(current_x) > 0.001 or abs(current_z) > 0.001:
                    chassis.write((json.dumps({"T": 13, "X": round(current_x, 3), "Z": round(current_z, 3)}) + "\n").encode())
                    was_moving = True
                    current_status = "MOVING"
                else:
                    current_status = "ACTIVE" if mode == "DRIVING" else "IDLE"
                    if was_moving:
                        chassis.write((json.dumps({"T": 13, "X": 0.0, "Z": 0.0}) + "\n").encode())
                        was_moving = False
                        current_x = 0.0
                        current_z = 0.0
                        
            except zmq.Again:
                time.sleep(0.01) 
                
            # 3. Broadcast telemetry
            if time.time() - last_telem_send > 0.1: 
                pub_socket.send_json({"voltage": last_v, "status": current_status})
                last_telem_send = time.time()
                
    finally:
        print("[CHASSIS] Shutting down...")
        chassis.write((json.dumps({"T": 13, "X": 0.0, "Z": 0.0}) + "\n").encode())
        chassis.close()
        sub_socket.close()
        pub_socket.close()
        context.term()

if __name__ == "__main__":
    start_chassis()