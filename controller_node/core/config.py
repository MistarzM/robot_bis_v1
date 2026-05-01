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
A1 = 45.0    
A2 = 43.0   
A3 = 150.0  
A4 = 52.0   
A5 = 100.0  
A6 = 199.5
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

# CHASSIS CONFIGURATION (UGV02)
CHASSIS_PORT = '/dev/ttyACM0'  
CHASSIS_BAUD = 115200
CHASSIS_MAX_SPEED = 0.4