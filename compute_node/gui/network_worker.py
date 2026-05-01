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

    def run(self):
        self.socket.connect(self.robot_url)

        while self.is_running:
            pad = self.gamepad.read_state()
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

            self.status_signal.emit(pad.get('connected', False), robot_online)
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
        self.socket.setsockopt(zmq.CONFLATE, 1) # Always fetch the freshest data
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
            time.sleep(0.02) # ~50 Hz refresh rate
                
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