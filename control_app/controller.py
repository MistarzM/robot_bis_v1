import pygame
import serial
import time
import sys

PORT = '/dev/cu.usbserial-0001'
BAUD = 115200

# home positions
home_pos = {
    0: 2147, # base
    1: 3547, # shoulder l (shoulder r [2] is mirrored)
    3: 1747, # upperarm
    4: 2147, # elbow
    5: 1547, # forearm 
    6: 2047, # wrist
    7: 2847, # gripper
}

# current working positions
pos = home_pos.copy()

# initialization
print(f"[INFO] connecting to esp32 on {PORT}...")
try:
    ser = serial.Serial(PORT, BAUD, timeout=0.1)
    time.sleep(2)
    print("[SUCC] esp32: connected successfully")
except Exception as e:
    print(f"[EXCT] {e}")
    sys.exit()

pygame.init()
pygame.joystick.init()

if pygame.joystick.get_count() == 0:
    print("[ERR] no gamepad detected - connect ps5 dualsense")
    sys.exit()

joystick = pygame.joystick.Joystick(0)
joystick.init()
print(f"[SUCC] gamepad connected: {joystick.get_name()}")

# helper methods
def send_cmd(servo_id, position):
    """sends movement command to esp32 via serial"""
    position = max(0, min(4095, int(position)))
    ser.write(f"{servo_id},{position}\n".encode('utf-8'))

def apply_deadzone(value, deadzone=0.15):
    """ignores small analog stick drifts"""
    if abs(value) < deadzone:
        return 0.0
    return value

def normalize_trigger(value):
    """converts ps5 trigger range from [-1.0, 1.0] to [0.0, 1.0]"""
    return (value + 1.0) / 2.0

# main loop [50 hz / 20ms update rate]
clock = pygame.time.Clock()
speed_multiplier = 6

print("[SUCC] system ready - use ps5 controller to move")

running = True
while running:
    pygame.event.pump()

    # first case - read incoming telemetry from esp32 
    while ser.in_waiting > 0:
        try:
            line = ser.readline().decode('utf-8').strip()
            if line:
                print(f"[ESP32] {line}")
        except:
            pass

    # second case - controller logic

    # right stick - base and shoulder
    axis_rx = apply_deadzone(joystick.get_axis(2))
    axis_ry = apply_deadzone(joystick.get_axis(3))
    
    pos[0] += axis_rx * speed_multiplier
    pos[1] -= axis_ry * speed_multiplier 

    # cross (0) / circle (1) -> upperarm (id 3)
    if joystick.get_button(0): 
        pos[3] += speed_multiplier
    if joystick.get_button(1): 
        pos[3] -= speed_multiplier

    # d-pad -> elbow (id 4) [left/right] & forearm (id 5) [up/down]
    if joystick.get_button(11): pos[5] += speed_multiplier # up
    if joystick.get_button(12): pos[5] -= speed_multiplier # down
    if joystick.get_button(13): pos[4] -= speed_multiplier # left
    if joystick.get_button(14): pos[4] += speed_multiplier # right

    # bumpers l1 (9) / r1 (10) -> wrist (id 6)
    if joystick.get_button(9):
        pos[6] -= speed_multiplier
    if joystick.get_button(10):
        pos[6] += speed_multiplier

    # triggers l2 (4) / r2 (5) -> gripper (id 7)
    trigger_l2 = normalize_trigger(joystick.get_axis(4))
    trigger_r2 = normalize_trigger(joystick.get_axis(5))
    
    if trigger_l2 > 0.05: 
        pos[7] -= (trigger_l2 * speed_multiplier)
    if trigger_r2 > 0.05: 
        pos[7] += (trigger_r2 * speed_multiplier)

    # third case - special commands
    
    # triangle (3) -> reset / smart homing sequence
    if joystick.get_button(3):
        print("\n[INFO] initiating hardware scan and smart homing...")
        
        # 1. trigger esp32 hardware scan
        ser.write(b"reset\n")
        time.sleep(1.0) # wait for esp32 to scan 8 servos (takes ~400ms)

        # 2. sequential homing (bottom to top logic to avoid collisions)
        homing_sequence = [0, 1, 3, 4, 5, 6, 7]
        
        for servo_id in homing_sequence:
            target = home_pos[servo_id]
            pos[servo_id] = target # update working variable
            
            if servo_id == 1:
                send_cmd(1, target)
                send_cmd(2, 4095 - target) # mirror for shoulder r
            else:
                send_cmd(servo_id, target)
                
            print(f"[INFO] homing joint id {servo_id}...")
            time.sleep(0.5) 
            
        print("[SUCC] homing sequence complete\n")
        time.sleep(0.5) # final debounce

    # square (2) -> stat / telemetry
    if joystick.get_button(2):
        print("\n[INFO] requesting telemetry from esp32")
        ser.write(b"stat\n")
        time.sleep(0.5)

    # fourth case - send movement commands
    send_cmd(0, pos[0])
    send_cmd(1, pos[1])
    send_cmd(2, 4095 - pos[1]) 
    send_cmd(3, pos[3])
    send_cmd(4, pos[4])
    send_cmd(5, pos[5])
    send_cmd(6, pos[6])
    send_cmd(7, pos[7])

    clock.tick(50)
