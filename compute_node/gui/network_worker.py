import cv2
import numpy as np
import time
import zmq
from PySide6.QtCore import QThread, Signal
from hardware.gamepad import GamepadController
from core import config
from ai_vision.object_detector import YoloDetector

class NetworkWorker(QThread):
    status_signal = Signal(bool, bool)

    def __init__(self):
        super().__init__()
        self.is_running = True
        self.gamepad = GamepadController()
        
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.robot_url = f"tcp://{config.ROBOT_IP}:{config.ZMQ_CONTROL_PORT}"
        self.socket.setsockopt(zmq.RCVTIMEO, 500)

        # Stan Wirtualnego Pada (GUI)
        self.vpad = {
            'lx': 0.0, 'ly': 0.0, 'rx': 0.0, 'ry': 0.0,
            'l2': 0.0, 'r2': 0.0,
            'btn_square': False, 'btn_triangle': False,
            'btn_circle': False, 'btn_cross': False,
            'dpad_up': False, 'dpad_down': False
        }

    def update_vpad_axis(self, axis, value):
        self.vpad[axis] = value

    def update_vpad_btn(self, btn, is_pressed):
        self.vpad[btn] = is_pressed

    def run(self):
        self.socket.connect(self.robot_url)

        while self.is_running:
            pad = self.gamepad.read_state()
            
            # KRYTYCZNA ZMIANA: Jeśli brak sprzętowego pada, ZAWSZE symulujemy 
            # wyzerowanego pada z 'connected': True. Dzięki temu serwer nie ignoruje
            # komend po puszczeniu przycisku (co powodowało jazdę w nieskończoność).
            if not pad.get('connected'):
                pad = {
                    'connected': True, 
                    'lx': 0.0, 'ly': 0.0, 'rx': 0.0, 'ry': 0.0,
                    'l2': 0.0, 'r2': 0.0,
                    'btn_square': False, 'btn_triangle': False,
                    'btn_circle': False, 'btn_cross': False,
                    'dpad_up': False, 'dpad_down': False
                }

            # Wstrzykiwanie wciśniętych przycisków z GUI
            for k, v in self.vpad.items():
                if type(v) == bool and v:
                    pad[k] = True
                elif type(v) == float and v != 0.0:
                    pad[k] = v

            payload = {"command": "CONTROL", "pad": pad}

            robot_online = False
            try:
                self.socket.send_json(payload)
                self.socket.recv_json() 
                robot_online = True
            except zmq.Again:
                robot_online = False
                self.socket.close()
                self.socket = self.context.socket(zmq.REQ)
                self.socket.setsockopt(zmq.RCVTIMEO, 500)
                self.socket.connect(self.robot_url)

            # Do interfejsu rzucamy prawdziwy status PADA fizycznego, żeby GUI wiedziało,
            # czy sterujemy sprzętem czy myszką.
            self.status_signal.emit(self.gamepad.connected, robot_online)
            time.sleep(0.02)

    def stop(self):
        self.is_running = False
        self.wait()

class TelemetryWorker(QThread):
    feedback_signal = Signal(dict)

    def __init__(self):
        super().__init__()
        self.is_running = True
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.setsockopt(zmq.CONFLATE, 1) 
        self.socket.setsockopt_string(zmq.SUBSCRIBE, "") 
        self.telemetry_url = f"tcp://{config.ROBOT_IP}:{config.ZMQ_FEEDBACK_PORT}"

    def run(self):
        self.socket.connect(self.telemetry_url)
        while self.is_running:
            try:
                data = self.socket.recv_json(flags=zmq.NOBLOCK)
                self.feedback_signal.emit(data)
            except zmq.Again:
                pass
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
        self.socket.setsockopt(zmq.CONFLATE, 1)
        self.socket.setsockopt(zmq.RCVTIMEO, 1000)
        self.socket.setsockopt_string(zmq.SUBSCRIBE, "") 
        self.video_url = f"tcp://{config.ROBOT_IP}:{config.ZMQ_VIDEO_PORT}"
        self.detector = YoloDetector()

    def run(self):
        print(f"[VIDEO] Connecting to {self.video_url} and starting AI analysis...")
        self.socket.connect(self.video_url)

        while self.is_running:
            try:
                frame_bytes = self.socket.recv()
                nparr = np.frombuffer(frame_bytes, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                if frame is not None:
                    annotated_frame, detections = self.detector.process_frame(frame)
                    _, buffer = cv2.imencode('.jpg', annotated_frame)
                    self.frame_signal.emit(buffer.tobytes())
                    
            except zmq.Again:
                pass 
                
    def stop(self):
        self.is_running = False
        self.wait()