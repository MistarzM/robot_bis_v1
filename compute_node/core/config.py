# --- NETWORK SETTINGS ---
ROBOT_IP = "192.168.55.107"  # hostname -I
ZMQ_CONTROL_PORT = "5555"      
ZMQ_VIDEO_PORT = "5556"        
ZMQ_FEEDBACK_PORT = "5557"   

# --- GAMEPAD  ---
BUTTON_MAP = {
    "CROSS": 0,
    "CIRCLE": 1,
    "SQUARE": 2,
    "TRIANGLE": 3,
    "L1": 9,
    "R1": 10,
    "SHARE": 4,
    "OPTIONS": 6,
    "PS_BTN": 5,
    "L3": 7,
    "R3": 8
}

AXIS_MAP = {
    "LX": 0,
    "LY": 1,
    "RX": 2,
    "RY": 3,
    "L2": 4,
    "R2": 5
}

# --- MOVEMENT PARAMETERS ---
LINEAR_SENSITIVITY = 2.0
ANGULAR_SENSITIVITY = 0.02
DEADZONE = 0.15