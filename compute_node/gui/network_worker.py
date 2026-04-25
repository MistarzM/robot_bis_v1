import time
import zmq
from PySide6.QtCore import QThread, Signal, QByteArray
from hardware.gamepad import GamepadController
from core import config

class NetworkWorker(QThread):
    status_signal = Signal(bool, bool)
    telemetry_signal = Signal(list)
    coords_signal = Signal(list)
    mode_signal = Signal(list, str)
    log_signal = Signal(list)

    def __init__(self):
        super().__init__()
        self.is_running = True
        self.gamepad = GamepadController()
        
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.robot_url = f"tcp://{config.ROBOT_IP}:{config.ROBOT_PORT}"
        self.socket.setsockopt(zmq.RCVTIMEO, 500)

    def run(self):
        self.socket.connect(self.robot_url)

        while self.is_running:
            pad = self.gamepad.read_state()
            payload = {"command": "CONTROL", "pad": pad}

            robot_online = False
            try:
                self.socket.send_json(payload)
                response = self.socket.recv_json()
                robot_online = True
                
                if response.get("status") == "OK":
                    self.telemetry_signal.emit(response.get("servos", []))
                    self.coords_signal.emit(response.get("coords", []))
                    self.mode_signal.emit(response.get("target", []), response.get("mode", ""))
                    
                    if "logs" in response and response["logs"]:
                        self.log_signal.emit(response["logs"])

            except zmq.Again:
                robot_online = False
                self.socket.close()
                self.socket = self.context.socket(zmq.REQ)
                self.socket.setsockopt(zmq.RCVTIMEO, 500)
                self.socket.connect(self.robot_url)

            self.status_signal.emit(pad.get('connected', False), robot_online)
            time.sleep(0.02)

    def stop(self):
        self.is_running = False
        self.wait()


class VideoWorker(QThread):
    frame_signal = Signal(bytes)

    def __init__(self):
        super().__init__()
        self.is_running = True
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.setsockopt(zmq.RCVTIMEO, 1000)
        self.socket.setsockopt_string(zmq.SUBSCRIBE, "") 
        self.video_url = f"tcp://{config.ROBOT_IP}:{config.VIDEO_PORT}"

    def run(self):
        print(f"[VIDEO] Connecting to {self.video_url}")
        self.socket.connect(self.video_url)

        while self.is_running:
            try:
                frame_bytes = self.socket.recv()
                self.frame_signal.emit(frame_bytes)
            except zmq.Again:
                pass # Brak klatki, czekamy dalej
                
    def stop(self):
        self.is_running = False
        self.wait()