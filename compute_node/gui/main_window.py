from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QTextEdit
from PySide6.QtCore import Qt
from gui.network_worker import NetworkWorker

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UGV02 - 6DOF Command Center")
        self.setFixedSize(880, 950) # Lekko powiększone, by pomieścić logi
        self.setStyleSheet("font-size: 14px;")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)

        self._build_mode_panel()
        self._build_status_panel()
        self._build_spatial_panel() 
        self._build_telemetry_panel()
        self._build_console_panel() # NOWY PANEL LOGÓW
        self.main_layout.addStretch()

        self.worker = NetworkWorker()
        self.worker.status_signal.connect(self.update_statuses)
        self.worker.telemetry_signal.connect(self.update_telemetry)
        self.worker.coords_signal.connect(self.update_coords) 
        self.worker.mode_signal.connect(self.update_target_ui)
        self.worker.log_signal.connect(self.append_logs)
        self.worker.start()

    def _build_mode_panel(self):
        mode_group = QGroupBox("Active Control Mode")
        mode_layout = QVBoxLayout()
        self.lbl_mode = QLabel("LOADING...")
        self.lbl_mode.setAlignment(Qt.AlignCenter)
        self.lbl_mode.setStyleSheet("font-size: 24px; font-weight: bold; padding: 10px; border-radius: 5px;")
        mode_layout.addWidget(self.lbl_mode)
        mode_group.setLayout(mode_layout)
        self.main_layout.addWidget(mode_group)

    def _build_status_panel(self):
        status_group = QGroupBox("System Status")
        status_layout = QHBoxLayout()
        self.lbl_gamepad = QLabel("Gamepad: DISCONNECTED")
        self.lbl_gamepad.setStyleSheet("color: red; font-weight: bold;")
        self.lbl_robot = QLabel("Robot Link: WAITING...")
        self.lbl_robot.setStyleSheet("color: orange; font-weight: bold;")
        status_layout.addWidget(self.lbl_gamepad)
        status_layout.addWidget(self.lbl_robot)
        status_group.setLayout(status_layout)
        self.main_layout.addWidget(status_group)

    def _build_spatial_panel(self):
        spatial_group = QGroupBox("Task Space & IK Target")
        spatial_layout = QVBoxLayout()
        self.coord_labels = {}
        
        self.lbl_target = QLabel("TARGET: X: 0.0 | Y: 0.0 | Z: 0.0 | Yaw: 0.00 | Pitch: 0.00 | Roll: 0.00")
        self.lbl_target.setStyleSheet("font-family: monospace; color: #ff5555; font-weight: bold; background: #222; padding: 5px;")
        spatial_layout.addWidget(self.lbl_target)
        
        points = ["Shoulder", "Elbow", "Wrist", "Gripper (EE)"]
        for point in points:
            row = QHBoxLayout()
            name = QLabel(f"{point}:")
            name.setFixedWidth(100)
            val = QLabel("X: 0.0 | Y: 0.0 | Z: 0.0")
            val.setStyleSheet("font-family: monospace; color: cyan; font-weight: bold;")
            row.addWidget(name)
            row.addWidget(val)
            spatial_layout.addLayout(row)
            self.coord_labels[point] = val
            
        spatial_group.setLayout(spatial_layout)
        self.main_layout.addWidget(spatial_group)
        
    def _build_telemetry_panel(self):
        telemetry_group = QGroupBox("Joint Space (Raw Values 0-4095)")
        telemetry_layout = QVBoxLayout()
        self.servo_labels = []
        servo_names = ["Base (0)", "Shoulder L (1)", "Upperarm (3)", 
                       "Forearm (4)", "Wrist Pitch (5)", "Wrist Roll (6)", "Gripper (7)"]
        for name in servo_names:
            row_layout = QHBoxLayout()
            name_label = QLabel(f"{name}:")
            name_label.setFixedWidth(120)
            value_label = QLabel("0")
            value_label.setStyleSheet("font-family: monospace; font-weight: bold;")
            row_layout.addWidget(name_label)
            row_layout.addWidget(value_label)
            row_layout.addStretch()
            telemetry_layout.addLayout(row_layout)
            self.servo_labels.append(value_label)
        telemetry_group.setLayout(telemetry_layout)
        self.main_layout.addWidget(telemetry_group)

    def _build_console_panel(self):
        console_group = QGroupBox("System Output / Logs")
        console_layout = QVBoxLayout()
        self.txt_console = QTextEdit()
        self.txt_console.setReadOnly(True)
        self.txt_console.setStyleSheet("background-color: #1e1e1e; color: #00ff00; font-family: monospace; font-size: 12px;")
        self.txt_console.setFixedHeight(120)
        console_layout.addWidget(self.txt_console)
        console_group.setLayout(console_layout)
        self.main_layout.addWidget(console_group)

    def update_statuses(self, pad_ok, serial_ok):
        self.lbl_gamepad.setText("Gamepad: CONNECTED" if pad_ok else "Gamepad: DISCONNECTED")
        self.lbl_gamepad.setStyleSheet(f"color: {'green' if pad_ok else 'red'}; font-weight: bold;")
        self.lbl_robot.setText("Robot Link: ACTIVE" if serial_ok else "Robot Link: OFF")
        self.lbl_robot.setStyleSheet(f"color: {'green' if serial_ok else 'orange'}; font-weight: bold;")

    def update_target_ui(self, t, mode):
        # Dokładnie te kolory, o które prosiłeś!
        colors = {
            "XYZ": ("#204a87", "#ffffff"),         # Niebieski
            "ORIENTATION": ("#c4a000", "#ffffff"), # Żółty/Musztardowy
            "DRIVING": ("#cc0000", "#ffffff"),     # Czerwony
            "AUTONOMOUS": ("#4e9a06", "#ffffff")   # Zielony
        }
        bg, fg = colors.get(mode, ("#555", "#fff"))
        self.lbl_mode.setText(f"[{mode}]")
        self.lbl_mode.setStyleSheet(f"font-size: 24px; font-weight: bold; padding: 10px; border-radius: 5px; background-color: {bg}; color: {fg};")
        
        if len(t) >= 6:
            self.lbl_target.setText(f"TARGET => X:{t[0]:.0f} | Y:{t[1]:.0f} | Z:{t[2]:.0f} | Yaw:{t[3]:.2f} | Pitch:{t[4]:.2f} | Roll:{t[5]:.2f}")

    def update_coords(self, coords_list):
        points = ["Shoulder", "Elbow", "Wrist", "Gripper (EE)"]
        # Aktualizuje wszystkie 4 koordynaty osobno!
        if len(coords_list) >= 4:
            for i, point in enumerate(points):
                c = coords_list[i]
                self.coord_labels[point].setText(f"X: {c[0]:>5.1f} | Y: {c[1]:>5.1f} | Z: {c[2]:>5.1f}")
            
    def update_telemetry(self, positions):
        if len(positions) == len(self.servo_labels):
            for i in range(len(positions)):
                self.servo_labels[i].setText(str(int(positions[i])))

    def append_logs(self, log_list):
        for log in log_list:
            self.txt_console.append(log)
            # Automatyczne przewijanie na sam dół
            scrollbar = self.txt_console.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

    def closeEvent(self, event):
        self.worker.stop()
        event.accept()