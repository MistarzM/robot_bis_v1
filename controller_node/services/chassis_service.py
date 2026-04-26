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
        print("[CHASSIS] Connected and ready.")
    except Exception as e:
        print(f"[CHASSIS ERROR] {e}")
        return

    was_moving = False
    current_status = "IDLE"
    last_v = 0.0
    last_telem_send = 0

    try:
        while True:
            # 1. Nasłuch Portu Szeregowego z UGV02 (aktualizuje zmienną last_v)
            if chassis.in_waiting > 0:
                line = chassis.readline().decode('utf-8', errors='ignore').strip()
                if "V" in line: 
                    try:
                        data = json.loads(line)
                        if "V" in data:
                            last_v = data["V"]
                    except: 
                        pass

            # 2. Nasłuch Komend (Aktualizuje jazdę i status)
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
                        current_status = "MOVING"
                    else:
                        current_status = "ACTIVE"
                        if was_moving:
                            chassis.write((json.dumps({"T": 13, "X": 0.0, "Z": 0.0}) + "\n").encode())
                            was_moving = False
                else:
                    current_status = "IDLE"
                    if was_moving:
                        chassis.write((json.dumps({"T": 13, "X": 0.0, "Z": 0.0}) + "\n").encode())
                        was_moving = False
                        
            except zmq.Again:
                pass 
                
            # 3. Stałe nadawanie do Mózgu (nawet jeśli napięcie się nie odświeżyło sprzętowo)
            if time.time() - last_telem_send > 0.1: # 10 FPS
                pub_socket.send_json({"voltage": last_v, "status": current_status})
                last_telem_send = time.time()
                
    finally:
        print("[CHASSIS] Shutting down...")
        chassis.close()
        sub_socket.close()
        pub_socket.close()
        context.term()

if __name__ == "__main__":
    start_chassis()