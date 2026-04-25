import math

# --- COMMUNICATION ---
PORT = '/dev/ttyUSB0'  
BAUD = 115200
ZMQ_PORT = "5555"
VIDEO_PORT = "5556"      

# --- MOVEMENT PARAMETERS ---
SPEED_LINEAR = 2.0    
SPEED_ANGULAR = 0.02  
MAX_STEP = 16          
GRIP_SPEED = 5

# --- ARM DIMENSION (mm) ---
A1 = 112.5
A2 = 75.0
A3 = 183.0
A4 = 16.0
A5 = 150.0
A6 = 199.5
MAX_REACH = A2 + A3 + A5 + A6 - 5.0

# --- PHYSICAL HOME & ZERO POSITION ---
HOME_POS = {
    0: 2047, 1: 3147, 3: 1847, 
    4: 2147, 5: 2247, 6: 2047, 7: 2847
}

ZERO_POS = {
    0: 2047,                                  
    1: 3147 - int(90.0 / 0.088),              
    3: 1847,                                  
    4: 2147,                                  
    5: 2247,                                  
    6: 2047,                                  
    7: 2847                                   
}