import math

# NETWORKING
# external network (Wi-Fi: Laptop <-> Raspberry Pi)
ZMQ_CONTROL_PORT  = "5555"
ZMQ_VIDEO_PORT    = "5556"
ZMQ_FEEDBACK_PORT = "5557"

# internal network (localhost: Inside Raspberry Pi)
ZMQ_LOCAL_COMMANDS  = "5558"
ZMQ_LOCAL_TELEMETRY = "5559"


# ARM
ARM_PORT = '/dev/ttyUSB0'
ARM_BAUD = 115200

SPEED_LINEAR  = 2.0
SPEED_ANGULAR = 0.02
MAX_STEP      = 16
GRIP_SPEED    = 10

# Arm link dimensions (mm)
A1 = 52.0
A2 = 50.5
A3 = 150.0
A4 = 51.0
A5 = 88.5
A6 = 179.0
MAX_REACH = A2 + A3 + A5 + A6 - 5.0


# joint identity
JOINT_NAMES = {
    0: "Base",
    1: "Shoulder L",
    2: "Shoulder R",
    3: "Elbow",
    4: "Forearm Roll",
    5: "Wrist Pitch",
    6: "Wrist Roll",
    7: "Gripper",
}

# hardware calibration
SERVO_MIN = 0
SERVO_MAX = 4095
SHOULDER_CALIB_ANGLE_DEG = 90.0

CALIB_BASE = 2048

# dual-drive shoulder (J2)
CALIB_SHOULDER_L = 1985
CALIB_SHOULDER_R = SERVO_MAX - CALIB_SHOULDER_L   
                                                  
CALIB_ELBOW        = 2400
CALIB_FOREARM_ROLL = 2148
CALIB_WRIST_PITCH  = 2300
CALIB_WRIST_ROLL   = 2048
CALIB_GRIPPER      = 2848

# elbow down - home
ELBOW_DOWN_POS = {
    0: CALIB_BASE,
    1: CALIB_SHOULDER_L,
    2: CALIB_SHOULDER_R,         
    3: CALIB_ELBOW,
    4: CALIB_FOREARM_ROLL,
    5: CALIB_WRIST_PITCH,
    6: CALIB_WRIST_ROLL,
    7: CALIB_GRIPPER,
}

# mathematical - zero pose - for the IK chain
ZERO_POS = {
    0: CALIB_BASE,
    1: CALIB_SHOULDER_L - int(SHOULDER_CALIB_ANGLE_DEG / 0.088),
    3: CALIB_ELBOW,
    4: CALIB_FOREARM_ROLL,
    5: CALIB_WRIST_PITCH,
    6: CALIB_WRIST_ROLL,
    7: CALIB_GRIPPER,
}


# joint software limits
JOINT_LIMITS = {
    0: (0,    4095),   # Base          — full range
    1: (1150, 3350),   # Shoulder L
    3: (1300, 3300),   # Elbow
    4: (0,    4095),   # Forearm Roll  — full range
    5: (1250, 3350),   # Wrist Pitch
    6: (0,    4095),   # Wrist Roll    — full range
    7: (1900, 3850),   # Gripper
}

# CHASSIS
CHASSIS_PORT       = '/dev/ttyACM0'
CHASSIS_BAUD       = 115200
CHASSIS_MAX_SPEED  = 0.2
CHASSIS_ACCEL_STEP = 0.01
CHASSIS_DECEL_STEP = 0.05
