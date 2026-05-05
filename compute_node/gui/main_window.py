from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QTextEdit, QGridLayout, QPushButton
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from gui.network_worker import NetworkWorker, VideoWorker, TelemetryWorker

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UGV02 - Compute Node Command Center")
        self.resize(1300, 800) 
        self.setStyleSheet("font-size: 13px; font-family: 'Menlo', 'Courier New', monospace;")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QHBoxLayout(central_widget)
        
        self.left_column = QVBoxLayout()
        self.right_column = QVBoxLayout()
        
        self.mode_buttons = {}
        self.xyz_controls = []
        self.rpy_controls = []
        self.drive_controls = []
        self.target_val_labels = {}

        self._build_mode_panel(self.left_column)
        self._build_system_status_panel(self.left_column)
        self._build_spatial_panel(self.left_column) 
        self._build_servo_status_panel(self.left_column)
        self._build_chassis_stats(self.left_column)
        self.left_column.addStretch()

        self._build_camera_panel(self.right_column)
        self._build_console_panel(self.right_column)

        self.main_layout.addLayout(self.left_column, 4)
        self.main_layout.addLayout(self.right_column, 5)

        self.worker = NetworkWorker()
        self.worker.status_signal.connect(self.update_pad_status)
        self.worker.start()

        self.telemetry_worker = TelemetryWorker()
        self.telemetry_worker.feedback_signal.connect(self.process_telemetry)
        self.telemetry_worker.start()

        self.video_worker = VideoWorker()
        self.video_worker.frame_signal.connect(self.update_camera_frame)
        self.video_worker.start()

    def _vpad_axis(self, axis, value):
        self.worker.update_vpad_axis(axis, value)

    def _vpad_btn(self, btn, state):
        self.worker.update_vpad_btn(btn, state)

    def _create_axis_block(self, name, axis_name, target_val_plus, target_val_minus, is_xyz=True):
        layout = QVBoxLayout()
        
        btn_plus = QPushButton(f"▲ (+)")
        btn_plus.setFixedSize(50, 30) 
        btn_plus.pressed.connect(lambda: self._vpad_axis(axis_name, target_val_plus))
        btn_plus.released.connect(lambda: self._vpad_axis(axis_name, 0.0))

        lbl_val = QLabel(f"{name}:\n0.0")
        lbl_val.setAlignment(Qt.AlignCenter)
        lbl_val.setStyleSheet("color: cyan; font-weight: bold; background: #222; border-radius: 4px; padding: 2px;")
        
        btn_minus = QPushButton(f"▼ (-)")
        btn_minus.setFixedSize(50, 30)
        btn_minus.pressed.connect(lambda: self._vpad_axis(axis_name, target_val_minus))
        btn_minus.released.connect(lambda: self._vpad_axis(axis_name, 0.0))

        layout.addWidget(btn_plus)
        layout.addWidget(lbl_val)
        layout.addWidget(btn_minus)
        
        controls = [btn_plus, btn_minus, lbl_val]
        if is_xyz:
            self.xyz_controls.extend(controls)
        else:
            self.rpy_controls.extend(controls)
            
        self.target_val_labels[name] = lbl_val
        return layout

    def _build_mode_panel(self, parent):
        group = QGroupBox("Active Control Mode")
        layout = QHBoxLayout()

        self.btn_xyz = QPushButton("XYZ")
        self.btn_rpy = QPushButton("RPY") 
        self.btn_drv = QPushButton("DRIVING")
        self.btn_auto = QPushButton("AUTONOMOUS")

        self.mode_buttons = {
            "XYZ": (self.btn_xyz, "#0055ff", "#002244", 'btn_square'),
            "RPY": (self.btn_rpy, "#d4a017", "#4a3b00", 'btn_triangle'),
            "DRIVING": (self.btn_drv, "#cc0000", "#4a0000", 'btn_circle'),
            "AUTONOMOUS": (self.btn_auto, "#4e9a06", "#1a3300", 'btn_cross')
        }

        for mode_name, (btn, active_col, pale_col, pad_btn) in self.mode_buttons.items():
            btn.setMinimumHeight(40)
            btn.setStyleSheet(f"background-color: {pale_col}; color: #888; font-weight: bold; border-radius: 5px; font-size: 14px;")
            
            btn.pressed.connect(lambda pb=pad_btn: self._vpad_btn(pb, True))
            btn.released.connect(lambda pb=pad_btn: self._vpad_btn(pb, False))
            layout.addWidget(btn)

        group.setLayout(layout)
        parent.addWidget(group)

    def _build_system_status_panel(self, parent):
        group = QGroupBox("System Status")
        layout = QGridLayout()
        
        self.status_labels = {
            "pad": QLabel("Gamepad: DISC"),
            "node": QLabel("Controller Node: WAIT"),
            "arm": QLabel("Arm: WAIT"),
            "chassis": QLabel("Chassis: WAIT")
        }
        
        layout.addWidget(self.status_labels["pad"], 0, 0)
        layout.addWidget(self.status_labels["node"], 0, 1)
        layout.addWidget(self.status_labels["arm"], 1, 0)
        layout.addWidget(self.status_labels["chassis"], 1, 1)
        
        for lbl in self.status_labels.values():
            lbl.setStyleSheet("color: orange; font-weight: bold;")
            
        group.setLayout(layout)
        parent.addWidget(group)

    def _build_spatial_panel(self, parent):
        group = QGroupBox("Task Space IK Target (Display & Control)")
        main_layout = QVBoxLayout()

        target_layout = QHBoxLayout()

        # ZMIANA: Zastąpienie pojedynczego przycisku dwoma (Zielony i Czerwony)
        preset_layout = QVBoxLayout()
        
        btn_home = QPushButton("HOME\nPOSITION")
        btn_home.setFixedSize(90, 45)
        btn_home.setStyleSheet("background-color: #1a3300; color: #4e9a06; font-weight: bold; border-radius: 5px;")
        btn_home.pressed.connect(lambda: self._vpad_btn('dpad_down', True))
        btn_home.released.connect(lambda: self._vpad_btn('dpad_down', False))

        btn_elbow = QPushButton("ELBOW DOWN\nPOSITION")
        btn_elbow.setFixedSize(90, 45)
        btn_elbow.setStyleSheet("background-color: #552222; color: #ff5555; font-weight: bold; border-radius: 5px;")
        btn_elbow.pressed.connect(lambda: self._vpad_btn('dpad_down', True))
        btn_elbow.released.connect(lambda: self._vpad_btn('dpad_down', False))
        
        preset_layout.addWidget(btn_home)
        preset_layout.addWidget(btn_elbow)
        preset_layout.addStretch() 
        target_layout.addLayout(preset_layout)

        v_sep1 = QWidget()
        v_sep1.setFixedWidth(2)
        v_sep1.setStyleSheet("background-color: #444; margin-left: 5px; margin-right: 5px;")
        target_layout.addWidget(v_sep1)
        
        target_layout.addLayout(self._create_axis_block("X", "ly", -0.4, 0.4, True))
        target_layout.addLayout(self._create_axis_block("Y", "lx", 0.4, -0.4, True))
        target_layout.addLayout(self._create_axis_block("Z", "ry", -0.4, 0.4, True))
        
        v_sep2 = QWidget()
        v_sep2.setFixedWidth(2)
        v_sep2.setStyleSheet("background-color: #444; margin-left: 5px; margin-right: 5px;")
        target_layout.addWidget(v_sep2)
        
        target_layout.addLayout(self._create_axis_block("Roll", "rx", -0.4, 0.4, False))
        target_layout.addLayout(self._create_axis_block("Pitch", "ly", 0.4, -0.4, False))
        target_layout.addLayout(self._create_axis_block("Yaw", "lx", 0.4, -0.4, False))
        
        main_layout.addLayout(target_layout)

        sep = QLabel()
        sep.setFixedHeight(2)
        sep.setStyleSheet("background-color: #333; margin-top: 5px; margin-bottom: 5px;")
        main_layout.addWidget(sep)

        self.coord_labels = {}
        points = ["Shoulder", "Elbow", "Wrist", "Gripper"]
        
        coord_layout = QGridLayout()
        for i, point in enumerate(points):
            name = QLabel(f"{point}:")
            name.setStyleSheet("color: #888; font-weight: bold;")
            val = QLabel("X: 0.0 | Y: 0.0 | Z: 0.0")
            val.setStyleSheet("color: cyan; font-weight: bold;")
            coord_layout.addWidget(name, i//2, (i%2)*2)
            coord_layout.addWidget(val, i//2, (i%2)*2 + 1)
            self.coord_labels[point] = val
            
        main_layout.addLayout(coord_layout)
        group.setLayout(main_layout)
        parent.addWidget(group)
        
    def _build_servo_status_panel(self, parent):
        group = QGroupBox("Servo Status Dashboard")
        layout = QGridLayout()
        layout.setVerticalSpacing(4) 
        
        headers = ["ID", "Position", "Temp", "Volt", "Curr", "Status"]
        for col, text in enumerate(headers):
            lbl = QLabel(text)
            lbl.setStyleSheet("color: #888; font-weight: bold;")
            layout.addWidget(lbl, 0, col)
            
        self.servo_data = []
        names = ["Bse(0)", "ShL(1)", "ShR(2)", "UAr(3)", "For(4)", "WPi(5)", "WRo(6)", "Grp(7)"]
        
        for row, name in enumerate(names, start=1):
            row_data = {
                "name": QLabel(name),
                "pos": QLabel("0"),
                "temp": QLabel("-- °C"), 
                "vol": QLabel("-- V"),
                "curr": QLabel("-- mA"),
                "stat": QLabel("INACTIVE")
            }
            layout.addWidget(row_data["name"], row, 0)
            layout.addWidget(row_data["pos"], row, 1)
            layout.addWidget(row_data["temp"], row, 2)
            layout.addWidget(row_data["vol"], row, 3)
            layout.addWidget(row_data["curr"], row, 4)
            layout.addWidget(row_data["stat"], row, 5)
            row_data["stat"].setStyleSheet("color: gray;")
            self.servo_data.append(row_data)
            
        group.setLayout(layout)
        parent.addWidget(group)

    def _build_chassis_stats(self, parent):
        chassis_layout = QHBoxLayout()
        
        bat_group = QGroupBox("Battery Status")
        bat_layout = QVBoxLayout()
        self.lbl_battery = QLabel("WAIT")
        self.lbl_battery.setAlignment(Qt.AlignCenter)
        self.lbl_battery.setStyleSheet("font-size: 24px; font-weight: bold; color: yellow;")
        bat_layout.addWidget(self.lbl_battery)
        bat_group.setLayout(bat_layout)
        
        drv_group = QGroupBox("Drive Controls (8-Way)")
        drive_layout = QGridLayout()
        
        btn_ul = QPushButton("↖"); btn_up = QPushButton("▲"); btn_ur = QPushButton("↗")
        btn_left = QPushButton("◀"); btn_stop = QPushButton("●"); btn_right = QPushButton("▶")
        btn_dl = QPushButton("↙"); btn_down = QPushButton("▼"); btn_dr = QPushButton("↘")
        
        btns = [btn_ul, btn_up, btn_ur, btn_left, btn_stop, btn_right, btn_dl, btn_down, btn_dr]
        for b in btns:
            b.setFixedSize(40, 40)
            self.drive_controls.append(b)

        def drive_action(ly, turn):
            self._vpad_axis('ly', ly)
            self._vpad_axis('lx', turn) 
            self._vpad_axis('rx', turn) 

        btn_up.pressed.connect(lambda: drive_action(-0.6, 0.0))
        btn_down.pressed.connect(lambda: drive_action(0.6, 0.0))
        btn_left.pressed.connect(lambda: drive_action(0.0, -0.6))
        btn_right.pressed.connect(lambda: drive_action(0.0, 0.6))
        
        btn_ul.pressed.connect(lambda: drive_action(-0.6, -0.6))
        btn_ur.pressed.connect(lambda: drive_action(-0.6, 0.6))
        btn_dl.pressed.connect(lambda: drive_action(0.6, -0.6))
        btn_dr.pressed.connect(lambda: drive_action(0.6, 0.6))

        for b in [btn_ul, btn_up, btn_ur, btn_left, btn_right, btn_dl, btn_down, btn_dr]:
            b.released.connect(lambda: drive_action(0.0, 0.0))

        btn_stop.setStyleSheet("color: red; font-weight: bold;")
        btn_stop.pressed.connect(lambda: drive_action(0.0, 0.0))

        drive_layout.addWidget(btn_ul, 0, 0); drive_layout.addWidget(btn_up, 0, 1); drive_layout.addWidget(btn_ur, 0, 2)
        drive_layout.addWidget(btn_left, 1, 0); drive_layout.addWidget(btn_stop, 1, 1); drive_layout.addWidget(btn_right, 1, 2)
        drive_layout.addWidget(btn_dl, 2, 0); drive_layout.addWidget(btn_down, 2, 1); drive_layout.addWidget(btn_dr, 2, 2)
        
        drive_layout.setAlignment(Qt.AlignCenter)
        drv_group.setLayout(drive_layout)
        
        chassis_layout.addWidget(bat_group, 1)
        chassis_layout.addWidget(drv_group, 1)
        
        parent.addLayout(chassis_layout)

    def _build_camera_panel(self, parent):
        group = QGroupBox("Live Video Feed")
        layout = QVBoxLayout()
        self.lbl_camera = QLabel("Waiting for stream...")
        self.lbl_camera.setAlignment(Qt.AlignCenter)
        self.lbl_camera.setStyleSheet("background-color: #000; color: #fff;")
        self.lbl_camera.setMinimumHeight(400)
        layout.addWidget(self.lbl_camera)
        group.setLayout(layout)
        parent.addWidget(group, 6)

    def _build_console_panel(self, parent):
        group = QGroupBox("System Feedback & Logs")
        layout = QVBoxLayout()
        self.txt_console = QTextEdit()
        self.txt_console.setReadOnly(True)
        self.txt_console.setStyleSheet("background-color: #1e1e1e; color: #00ff00;")
        layout.addWidget(self.txt_console)
        group.setLayout(layout)
        parent.addWidget(group, 4)

    def update_pad_status(self, pad_ok, _):
        self.status_labels["pad"].setText("Gamepad: CONNECTED" if pad_ok else "Gamepad: DISCONNECTED")
        self.status_labels["pad"].setStyleSheet(f"color: {'#4e9a06' if pad_ok else 'red'}; font-weight: bold;")

    def process_telemetry(self, data):
        mode = data.get("mode", "UNKNOWN")
        
        for m_name, (btn, active_col, pale_col, _) in self.mode_buttons.items():
            if mode == m_name:
                btn.setStyleSheet(f"background-color: {active_col}; color: white; font-weight: bold; border-radius: 5px; font-size: 15px;")
            else:
                btn.setStyleSheet(f"background-color: {pale_col}; color: #888; font-weight: bold; border-radius: 5px; font-size: 13px;")
            
        is_xyz = (mode == "XYZ")
        is_rpy = (mode == "RPY")
        is_drv = (mode == "DRIVING")
        
        for c in self.xyz_controls: c.setEnabled(is_xyz)
        for c in self.rpy_controls: c.setEnabled(is_rpy)
        for c in self.drive_controls: c.setEnabled(is_drv)
        
        t = data.get("target", [0,0,0,0,0,0])
        if len(t) >= 6 and "X" in self.target_val_labels:
            self.target_val_labels["X"].setText(f"X:\n{t[0]:.1f}")
            self.target_val_labels["Y"].setText(f"Y:\n{t[1]:.1f}")
            self.target_val_labels["Z"].setText(f"Z:\n{t[2]:.1f}")
            self.target_val_labels["Roll"].setText(f"Rol:\n{t[5]:.2f}")
            self.target_val_labels["Pitch"].setText(f"Pit:\n{t[4]:.2f}")
            self.target_val_labels["Yaw"].setText(f"Yaw:\n{t[3]:.2f}")

        self.status_labels["node"].setText(f"Controller: {data.get('node_status')}")
        self.status_labels["node"].setStyleSheet("color: #4e9a06; font-weight: bold;")
        
        arm_s = data.get('arm_status', 'WAIT')
        self.status_labels["arm"].setText(f"Arm: {arm_s}")
        self.status_labels["arm"].setStyleSheet(f"color: {'cyan' if 'MOVING' in arm_s else '#4e9a06' if arm_s == 'ACTIVE' else 'gray'}; font-weight: bold;")
        
        chas_s = data.get('chassis_status', 'WAIT')
        self.status_labels["chassis"].setText(f"Chassis: {chas_s}")
        self.status_labels["chassis"].setStyleSheet(f"color: {'cyan' if chas_s == 'MOVING' else '#4e9a06' if chas_s == 'ACTIVE' else 'gray'}; font-weight: bold;")
        
        coords = data.get("coords", [])
        if len(coords) >= 4:
            pts = ["Shoulder", "Elbow", "Wrist", "Gripper"]
            for i, pt in enumerate(pts):
                self.coord_labels[pt].setText(f"X: {coords[i][0]:>5.1f} | Y: {coords[i][1]:>5.1f} | Z: {coords[i][2]:>5.1f}")

        # ZMIANA: Dynamiczne kolorowanie napięcia na poszczególnych serwach
        servos = data.get("servos", [])
        if len(servos) == len(self.servo_data):
            for i, s_data in enumerate(servos):
                self.servo_data[i]["pos"].setText(str(s_data["pos"]))
                self.servo_data[i]["temp"].setText(f"{s_data['temp']} °C" if s_data['temp'] != '--' else "-- °C")
                
                # --- Logika Koloru Voltów ---
                v_str = s_data['volt']
                if v_str != '--':
                    try:
                        v_float = float(v_str)
                        if 11.0 <= v_float <= 12.6:
                            self.servo_data[i]["vol"].setStyleSheet("color: #4e9a06; font-weight: bold;") # Zielony
                        elif 10.5 <= v_float < 11.0:
                            self.servo_data[i]["vol"].setStyleSheet("color: #d4a017; font-weight: bold;") # Żółty
                        else:
                            self.servo_data[i]["vol"].setStyleSheet("color: #ff5555; font-weight: bold;") # Czerwony
                        self.servo_data[i]["vol"].setText(f"{v_str} V")
                    except ValueError:
                        self.servo_data[i]["vol"].setStyleSheet("color: #888;")
                        self.servo_data[i]["vol"].setText(f"{v_str} V")
                else:
                    self.servo_data[i]["vol"].setStyleSheet("color: #888;")
                    self.servo_data[i]["vol"].setText("-- V")

                self.servo_data[i]["curr"].setText(f"{s_data['curr']} mA" if s_data['curr'] != '--' else "-- mA")
                
                hw_status = s_data.get('status', 'OK')
                if hw_status == 'ERROR':
                    self.servo_data[i]["stat"].setText("OFFLINE")
                    self.servo_data[i]["stat"].setStyleSheet("color: #ff5555; font-weight: bold;")
                else:
                    if arm_s == "IDLE":
                        self.servo_data[i]["stat"].setText("IDLE")
                        self.servo_data[i]["stat"].setStyleSheet("color: gray;")
                    else:
                        self.servo_data[i]["stat"].setText("ACTIVE")
                        self.servo_data[i]["stat"].setStyleSheet("color: #4e9a06;")

        chas_data = data.get("chassis_data", {})
        volts = chas_data.get("voltage", 0.0)
        self.lbl_battery.setText(f"{volts:.2f} V")
        self.lbl_battery.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {'red' if volts > 0 and volts < 10.5 else '#4e9a06'};")

        for log in data.get("logs", []):
            self.txt_console.append(log)
            sb = self.txt_console.verticalScrollBar()
            sb.setValue(sb.maximum())

    def update_camera_frame(self, frame_bytes):
        pixmap = QPixmap()
        pixmap.loadFromData(frame_bytes)
        self.lbl_camera.setPixmap(pixmap.scaled(self.lbl_camera.width(), self.lbl_camera.height(), Qt.KeepAspectRatio))

    def closeEvent(self, event):
        self.worker.stop()
        self.telemetry_worker.stop()
        self.video_worker.stop()
        event.accept()