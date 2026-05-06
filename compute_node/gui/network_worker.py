import cv2
import numpy as np
import time
import zmq
from PySide6.QtCore import QThread, Signal
from hardware.gamepad import GamepadController
from core import config
from ai_vision.object_detector import YoloDetector

BUTTON_DICT = {
    "BTN_0": "Cross (X)",
    "BTN_1": "Circle (O)",
    "BTN_2": "Square (□)",
    "BTN_3": "Triangle (△)",
    "BTN_4": "Share",
    "BTN_5": "PS Button",
    "BTN_6": "Options",
    "BTN_7": "L3",
    "BTN_8": "R3",
    "BTN_9": "L1",
    "BTN_10": "R1",
    "BTN_11": "D-Pad Up (↑)",   
    "BTN_12": "D-Pad Down (↓)", # Tutaj mapuje się krzyżak w dół na PS5/Mac
    "BTN_13": "D-Pad Left (←)",
    "BTN_14": "D-Pad Right (→)",
    "HAT_0_UP": "D-Pad Up (↑)",
    "HAT_0_DOWN": "D-Pad Down (↓)",
    "HAT_0_LEFT": "D-Pad Left (←)",
    "HAT_0_RIGHT": "D-Pad Right (→)",
    "AXIS_4_POS": "L2 Trigger",
    "AXIS_5_POS": "R2 Trigger",
    "UNASSIGNED": "UNASSIGNED"
}

class NetworkWorker(QThread):
    status_signal = Signal(bool, bool)
    mapping_updated_signal = Signal(dict)

    def __init__(self):
        super().__init__()
        self.is_running = True
        self.gamepad = GamepadController()
        
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.robot_url = f"tcp://{config.ROBOT_IP}:{config.ZMQ_CONTROL_PORT}"
        self.socket.setsockopt(zmq.RCVTIMEO, 500)

        self.vpad = {
            'lx': 0.0, 'ly': 0.0, 'rx': 0.0, 'ry': 0.0,
            'btn_square': False, 'btn_triangle': False,
            'btn_circle': False, 'btn_cross': False,
            'dpad_down': False
        }
        
        # ZMIANA: Zaktualizowane domyślne mapowanie pod pada PS5
        self.pad_mapping = {
            'XYZ': 'BTN_2',           
            'RPY': 'BTN_3',           
            'DRIVING': 'BTN_1',       
            'AUTONOMOUS': 'BTN_0',    
            'HOMING': 'BTN_12',       # Było HAT_0_DOWN, teraz jest domyślnie pod pada PS5
            'GRIP_OPEN': 'AXIS_5_POS',
            'GRIP_CLOSE': 'AXIS_4_POS'
        }
        self.assigning_action = None
        self.mapping_mode = False

    def get_friendly_name(self, raw_name):
        return BUTTON_DICT.get(raw_name, raw_name)

    def request_assignment(self, action):
        self.assigning_action = action

    def update_vpad_axis(self, axis, value):
        self.vpad[axis] = value

    def update_vpad_btn(self, btn, is_pressed):
        self.vpad[btn] = is_pressed

    def run(self):
        self.socket.connect(self.robot_url)

        while self.is_running:
            raw = self.gamepad.read_raw_state()
            
            if self.assigning_action and raw:
                pressed = self.gamepad.get_pressed_input(raw)
                if pressed:
                    for k, v in list(self.pad_mapping.items()):
                        if v == pressed:
                            self.pad_mapping[k] = "UNASSIGNED"
                            
                    self.pad_mapping[self.assigning_action] = pressed
                    self.assigning_action = None
                    self.mapping_updated_signal.emit(self.pad_mapping)
                    time.sleep(0.3) 

            pad = {'connected': False, 'lx': 0.0, 'ly': 0.0, 'rx': 0.0, 'ry': 0.0}
            
            def is_active(mapping_key):
                hw = self.pad_mapping.get(mapping_key)
                if not hw or hw == "UNASSIGNED": return False
                try:
                    if hw.startswith("BTN_"):
                        idx = int(hw.split("_")[1])
                        if idx < len(raw['buttons']): return raw['buttons'][idx]
                    if hw.startswith("HAT_"):
                        idx, dir = int(hw.split("_")[1]), hw.split("_")[2]
                        hx, hy = raw['hats'][idx]
                        if dir == "UP": return hy == 1
                        if dir == "DOWN": return hy == -1
                        if dir == "LEFT": return hx == -1
                        if dir == "RIGHT": return hx == 1
                    if hw.startswith("AXIS_"):
                        idx, dir = int(hw.split("_")[1]), hw.split("_")[2]
                        val = raw['axes'][idx]
                        if dir == "POS": return val > 0.5
                except: pass
                return False

            if raw:
                pad['connected'] = True
                def get_ax(idx):
                    val = raw['axes'][idx] if idx < len(raw['axes']) else 0.0
                    return 0.0 if abs(val) < 0.15 else val
                
                if not self.mapping_mode:
                    pad['lx'] = get_ax(0)
                    pad['ly'] = get_ax(1)
                    pad['rx'] = get_ax(2)
                    pad['ry'] = get_ax(3)

            if not pad.get('connected'): pad['connected'] = True 
                
            for ax in ['lx', 'ly', 'rx', 'ry']:
                if self.vpad[ax] != 0.0: pad[ax] = self.vpad[ax]

            if not self.mapping_mode:
                pad['btn_square'] = (raw and is_active('XYZ')) or self.vpad['btn_square']
                pad['btn_triangle'] = (raw and is_active('RPY')) or self.vpad['btn_triangle']
                pad['btn_circle'] = (raw and is_active('DRIVING')) or self.vpad['btn_circle']
                pad['btn_cross'] = (raw and is_active('AUTONOMOUS')) or self.vpad['btn_cross']
                pad['dpad_down'] = (raw and is_active('HOMING')) or self.vpad['dpad_down']
                pad['r2'] = 1.0 if (raw and is_active('GRIP_OPEN')) else 0.0
                pad['l2'] = 1.0 if (raw and is_active('GRIP_CLOSE')) else 0.0
            else:
                pad['btn_square'] = False; pad['btn_triangle'] = False
                pad['btn_circle'] = False; pad['btn_cross'] = False; pad['dpad_down'] = False
                pad['r2'] = 0.0; pad['l2'] = 0.0

            payload = {"command": "CONTROL", "pad": pad}
            robot_online = False
            try:
                self.socket.send_json(payload)
                self.socket.recv_json() 
                robot_online = True
            except zmq.Again:
                self.socket.close()
                self.socket = self.context.socket(zmq.REQ)
                self.socket.setsockopt(zmq.RCVTIMEO, 500)
                self.socket.connect(self.robot_url)

            self.status_signal.emit(True if raw else False, robot_online)
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
            try: data = self.socket.recv_json(flags=zmq.NOBLOCK); self.feedback_signal.emit(data)
            except zmq.Again: pass
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
            except zmq.Again: pass 
    def stop(self):
        self.is_running = False
        self.wait()