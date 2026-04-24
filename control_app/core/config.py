# core/config.py
import math

# Komunikacja
PORT = '/dev/cu.usbserial-0001'
BAUD = 115200

# Prędkości
SPEED_LINEAR = 2.0    
SPEED_ANGULAR = 0.02  
MAX_STEP = 16 

# Wymiary ramienia (mm)
A1 = 112.5
A2 = 75.0
A3 = 183.0
A4 = 16.0
A5 = 150.0
A6 = 199.5
MAX_REACH = A2 + A3 + A5 + A6 - 5.0

# Physical Home Position (Kształt litery L zdefiniowany przez Ciebie)
HOME_POS = {
    0: 2047, 1: 3147, 3: 1847, 
    4: 2147, 5: 2247, 6: 2047, 7: 2847
}

# Zero calibration
ZERO_POS = {
    0: 2047,                                  
    1: 3147 - int(90.0 / 0.088),              
    3: 1847,                                  
    4: 2147,                                  
    5: 2247,                                  
    6: 2047,                                  
    7: 2847                                   
}