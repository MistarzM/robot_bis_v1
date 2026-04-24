# hardware/gamepad.py
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
import pygame

class GamepadController:
    def __init__(self):
        pygame.init()
        pygame.joystick.init()
        self.joystick = None
        self.connected = False

    def _apply_deadzone(self, value, deadzone=0.15):
        return 0.0 if abs(value) < deadzone else value

    def _normalize_trigger(self, value):
        return (value + 1.0) / 2.0

    def read_state(self):
        pygame.event.pump()
        
        if not self.connected:
            if pygame.joystick.get_count() > 0:
                self.joystick = pygame.joystick.Joystick(0)
                self.joystick.init()
                self.connected = True
                print(f"[SUCC] Gamepad connected: {self.joystick.get_name()}")
            else:
                return {'connected': False}

        try:
            def safe_axis(axis_id):
                return self.joystick.get_axis(axis_id) if axis_id < self.joystick.get_numaxes() else 0.0
                
            def safe_btn(btn_id):
                return self.joystick.get_button(btn_id) if btn_id < self.joystick.get_numbuttons() else False

            dpad_up, dpad_down, dpad_left, dpad_right = False, False, False, False
            if self.joystick.get_numhats() > 0:
                hx, hy = self.joystick.get_hat(0)
                dpad_up, dpad_down = (hy == 1), (hy == -1)
                dpad_left, dpad_right = (hx == -1), (hx == 1)
            else:
                dpad_up, dpad_down = safe_btn(11), safe_btn(12)
                dpad_left, dpad_right = safe_btn(13), safe_btn(14)

            return {
                'connected': True,
                'lx': self._apply_deadzone(safe_axis(0)), 
                'ly': self._apply_deadzone(safe_axis(1)),
                'rx': self._apply_deadzone(safe_axis(2)),
                'ry': self._apply_deadzone(safe_axis(3)),
                'btn_cross': safe_btn(0),
                'btn_circle': safe_btn(1),
                'btn_square': safe_btn(2),
                'btn_triangle': safe_btn(3),
                'dpad_up': dpad_up,
                'dpad_down': dpad_down,
                'dpad_left': dpad_left,
                'dpad_right': dpad_right,
                'l1': safe_btn(9),
                'r1': safe_btn(10),
                'l2': self._normalize_trigger(safe_axis(4)),
                'r2': self._normalize_trigger(safe_axis(5)),
            }
            
        except Exception as e:
            print(f"[ERR] Connection lost during read: {e}")
            self.connected = False
            self.joystick = None
            return {'connected': False}