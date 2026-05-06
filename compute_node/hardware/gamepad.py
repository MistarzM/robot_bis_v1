import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
import pygame

class GamepadController:
    def __init__(self):
        pygame.init()
        pygame.joystick.init()
        self.joystick = None
        self.connected = False

    def read_raw_state(self):
        pygame.event.pump()
        if not self.connected:
            if pygame.joystick.get_count() > 0:
                self.joystick = pygame.joystick.Joystick(0)
                self.joystick.init()
                self.connected = True
            return None

        try:
            state = {
                'buttons': [self.joystick.get_button(i) for i in range(self.joystick.get_numbuttons())],
                'axes': [self.joystick.get_axis(i) for i in range(self.joystick.get_numaxes())],
                'hats': [self.joystick.get_hat(i) for i in range(self.joystick.get_numhats())]
            }
            return state
        except:
            self.connected = False
            return None

    def get_pressed_input(self, state):
        """Wychwytuje pierwszy wciśnięty element (do procesu mapowania)"""
        if not state: return None
        for i, b in enumerate(state['buttons']):
            if b: return f"BTN_{i}"
            
        for i, h in enumerate(state['hats']):
            if h[1] == 1: return f"HAT_{i}_UP"
            if h[1] == -1: return f"HAT_{i}_DOWN"
            if h[0] == -1: return f"HAT_{i}_LEFT"
            if h[0] == 1: return f"HAT_{i}_RIGHT"
            
        for i, a in enumerate(state['axes']):
            # Ignorujemy gałki (0-3). Pozwalamy na mapowanie tylko triggerów (4,5)
            if i in [4, 5]: 
                if a > 0.5: return f"AXIS_{i}_POS"
        return None