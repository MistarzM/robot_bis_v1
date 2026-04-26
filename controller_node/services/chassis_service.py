import serial
import zmq
import json
import time
from core import config

def start_chassis():
    # Setup internal subscriber to listen for gamepad data from arm_service
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.connect(f"tcp://127.0.0.1:{config.ZMQ_LOCAL_PORT}")
    socket.setsockopt_string(zmq.SUBSCRIBE, "")

    print(f"[CHASSIS] Connecting to UGV02 on {config.CHASSIS_PORT}...")
    try:
        chassis = serial.Serial(config.CHASSIS_PORT, config.CHASSIS_BAUD, timeout=0.1)
        time.sleep(2)
        print("[CHASSIS] Connected to platform successfully.")
    except Exception as e:
        print(f"[CHASSIS ERROR] Port failed: {e}")
        return

    def drive(x, z):
        cmd = {"T": 13, "X": x, "Z": z}
        try:
            chassis.write((json.dumps(cmd) + "\n").encode('utf-8'))
        except Exception:
            pass

    was_moving = False

    try:
        while True:
            msg = socket.recv_json()
            pad = msg.get("pad", {})
            mode = msg.get("mode", "")

            if mode == "DRIVING" and pad.get("connected"):
                # Calculate speeds (invert axis for natural driving feel)
                drive_x = -pad.get("ly", 0.0) * config.CHASSIS_MAX_SPEED
                drive_z = -pad.get("rx", 0.0) * config.CHASSIS_MAX_SPEED

                # Deadzone check
                if abs(drive_x) > 0.05 or abs(drive_z) > 0.05:
                    drive(drive_x, drive_z)
                    was_moving = True
                else:
                    if was_moving:
                        drive(0.0, 0.0)
                        was_moving = False
            else:
                # Safety stop when switching modes
                if was_moving:
                    drive(0.0, 0.0)
                    was_moving = False
                    
    except KeyboardInterrupt:
        pass
    finally:
        print("[CHASSIS] Shutting down...")
        drive(0.0, 0.0)
        chassis.close()
        socket.close()
        context.term()

if __name__ == "__main__":
    start_chassis()