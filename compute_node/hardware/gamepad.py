import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
import pygame
from core import config

class GamepadController:
    def __init__(self):
        pygame.init()
        pygame.joystick.init()
        self.joystick = None
        self.connected = False

    def read_state(self):
        pygame.event.pump()
        if not self.connected:
            if pygame.joystick.get_count() > 0:
                self.joystick = pygame.joystick.Joystick(0)
                self.joystick.init()
                self.connected = True
            return {'connected': False}

        try:
            def get_ax(name):
                val = self.joystick.get_axis(config.AXIS_MAP[name])
                return 0.0 if abs(val) < config.DEADZONE else val

            def get_btn(name):
                return self.joystick.get_button(config.BUTTON_MAP[name])

            # ZABEZPIECZENIE D-PADA: Sprawdzamy hat, a jak nie ma, to przyciski 11-14
            d_up, d_down = False, False
            if self.joystick.get_numhats() > 0:
                hx, hy = self.joystick.get_hat(0)
                d_up = (hy == 1)
                d_down = (hy == -1)
            else:
                d_up = self.joystick.get_button(11) if self.joystick.get_numbuttons() > 11 else False
                d_down = self.joystick.get_button(12) if self.joystick.get_numbuttons() > 12 else False

            return {
                'connected': True,
                'lx': get_ax("LX"), 'ly': get_ax("LY"),
                'rx': get_ax("RX"), 'ry': get_ax("RY"),
                'l2': (self.joystick.get_axis(config.AXIS_MAP["L2"]) + 1.0) / 2.0,
                'r2': (self.joystick.get_axis(config.AXIS_MAP["R2"]) + 1.0) / 2.0,
                'btn_square': get_btn("SQUARE"),
                'btn_triangle': get_btn("TRIANGLE"),
                'btn_circle': get_btn("CIRCLE"),
                'btn_cross': get_btn("CROSS"),
                'dpad_up': d_up,
                'dpad_down': d_down,
            }
        except:
            self.connected = False
            return {'connected': False}