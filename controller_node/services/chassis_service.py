import serial
import zmq
import json
import time
from core import config

def start_chassis():
    context = zmq.Context()
    
    # Listen for local commands from Arm
    sub_socket = context.socket(zmq.SUB)
    sub_socket.connect(f"tcp://127.0.0.1:{config.ZMQ_LOCAL_COMMANDS}")
    sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")

    # Broadcast local telemetry (battery) back to Arm
    pub_socket = context.socket(zmq.PUB)
    pub_socket.bind(f"tcp://127.0.0.1:{config.ZMQ_LOCAL_TELEMETRY}")

    print(f"[CHASSIS] Connecting to UGV02 on {config.CHASSIS_PORT}...")
    try:
        chassis = serial.Serial(config.CHASSIS_PORT, config.CHASSIS_BAUD, timeout=0.01)
        time.sleep(2)
        print("[CHASSIS] Connected and ready.")
    except Exception as e:
        print(f"[CHASSIS ERROR] {e}")
        return

    was_moving = False

    try:
        while True:
            # 1. Read Hardware Telemetry
            if chassis.in_waiting > 0:
                line = chassis.readline().decode('utf-8', errors='ignore').strip()
                if line.startswith('{'): 
                    try:
                        data = json.loads(line)
                        pub_socket.send_json({"voltage": data.get("V", 0.0)})
                    except: 
                        pass

            # 2. Process Local Commands
            try:
                msg = sub_socket.recv_json(flags=zmq.NOBLOCK)
                pad = msg.get("pad", {})
                mode = msg.get("mode", "")

                if mode == "DRIVING" and pad.get("connected"):
                    drive_x = -pad.get("ly", 0.0) * config.CHASSIS_MAX_SPEED
                    drive_z = -pad.get("lx", 0.0) * config.CHASSIS_MAX_SPEED

                    if abs(drive_x) > 0.05 or abs(drive_z) > 0.05:
                        chassis.write((json.dumps({"T": 13, "X": drive_x, "Z": drive_z}) + "\n").encode())
                        was_moving = True
                    elif was_moving:
                        chassis.write((json.dumps({"T": 13, "X": 0.0, "Z": 0.0}) + "\n").encode())
                        was_moving = False
                else:
                    if was_moving:
                        chassis.write((json.dumps({"T": 13, "X": 0.0, "Z": 0.0}) + "\n").encode())
                        was_moving = False
                        
            except zmq.Again:
                pass 
                
    finally:
        print("[CHASSIS] Shutting down...")
        chassis.close()
        sub_socket.close()
        pub_socket.close()
        context.term()

if __name__ == "__main__":
    start_chassis()