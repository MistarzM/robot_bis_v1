import math

# EXTERNAL NETWORK (Wi-Fi: Laptop <-> Raspberry Pi) 
ZMQ_CONTROL_PORT = "5555"      
ZMQ_VIDEO_PORT = "5556"        
ZMQ_FEEDBACK_PORT = "5557"     

# INTERNAL NETWORK (Localhost: Inside Raspberry Pi) 
ZMQ_LOCAL_COMMANDS = "5558"    
ZMQ_LOCAL_TELEMETRY = "5559"

# ARM CONFIGURATION 
ARM_PORT = '/dev/ttyUSB0'   
ARM_BAUD = 115200

SPEED_LINEAR = 2.0    
SPEED_ANGULAR = 0.02  
MAX_STEP = 16          
GRIP_SPEED = 5

# Arm dimensions (mm)
A1 = 52.0    
A2 = 50.5   
A3 = 150.0  
A4 = 51.0   
A5 = 88.5  
A6 = 179.0
MAX_REACH = A2 + A3 + A5 + A6 - 5.0

# Hardware calibration 
SERVO_MIN = 0
SERVO_MAX = 4095
SHOULDER_CALIB_ANGLE_DEG = 90.0 

CALIB_BASE        = 2048
CALIB_SHOULDER    = 1985  
CALIB_ELBOW       = 2400
CALIB_FOREARM     = 2148
CALIB_WRIST_PITCH = 2300
CALIB_WRIST_ROLL  = 2048
CALIB_END_EFFECTOR = 2848 

# base position
ELBOW_DOWN_POS = {
    0: CALIB_BASE, 
    1: CALIB_SHOULDER, 
    2: SERVO_MAX - CALIB_SHOULDER,  
    3: CALIB_ELBOW, 
    4: CALIB_FOREARM, 
    5: CALIB_WRIST_PITCH, 
    6: CALIB_WRIST_ROLL, 
    7: CALIB_END_EFFECTOR
}

# mathematical zero (for ik)
ZERO_POS = {
    0: CALIB_BASE,                                  
    1: CALIB_SHOULDER - int(SHOULDER_CALIB_ANGLE_DEG / 0.088), 
    3: CALIB_ELBOW,
    4: CALIB_FOREARM,                                  
    5: CALIB_WRIST_PITCH,                                  
    6: CALIB_WRIST_ROLL,                                  
    7: CALIB_END_EFFECTOR                                   
}

JOINT_LIMITS = {
    0: (0, 4095),       # Base (full range)
    1: (1200, 3400),    # Shoulder L 
    3: (1300, 3300),    # Elbow 
    4: (0, 4095),       # Forearm (full range)
    5: (1250, 3350),    # Wrist Pitch
    6: (0, 4095),       # Wrist Roll (full range)
    7: (1900, 3850)     # Gripper 
}

# CHASSIS CONFIGURATION
CHASSIS_PORT = '/dev/ttyACM0'  
CHASSIS_BAUD = 115200
CHASSIS_MAX_SPEED = 0.4
CHASSIS_ACCEL_STEP = 0.01 
CHASSIS_DECEL_STEP = 0.05  