from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QTextEdit
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from gui.network_worker import NetworkWorker, VideoWorker

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UGV02 - 6DOF Command Center")
        # Startujemy z dużym oknem (zoptymalizowane pod FullHD/Macbooka)
        self.resize(1200, 800) 
        self.setStyleSheet("font-size: 14px;")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # GŁÓWNY UKŁAD POZIOMY (Dwie kolumny)
        self.main_layout = QHBoxLayout(central_widget)
        
        self.left_column = QVBoxLayout()
        self.right_column = QVBoxLayout()
        
        # Budowa Lewej Kolumny
        self._build_mode_panel(self.left_column)
        self._build_status_panel(self.left_column)
        self._build_spatial_panel(self.left_column) 
        self._build_telemetry_panel(self.left_column)
        self._build_chassis_placeholder(self.left_column)
        self.left_column.addStretch()

        # Budowa Prawej Kolumny
        self._build_camera_panel(self.right_column)
        self._build_console_panel(self.right_column)

        # Dodanie kolumn do głównego okna (lewa zajmuje 1 część, prawa 2 części)
        self.main_layout.addLayout(self.left_column, 1)
        self.main_layout.addLayout(self.right_column, 2)

        # Uruchomienie wątków (Kontrola + Wideo)
        self.worker = NetworkWorker()
        self.worker.status_signal.connect(self.update_statuses)
        self.worker.telemetry_signal.connect(self.update_telemetry)
        self.worker.coords_signal.connect(self.update_coords) 
        self.worker.mode_signal.connect(self.update_target_ui)
        self.worker.log_signal.connect(self.append_logs)
        self.worker.start()

        self.video_worker = VideoWorker()
        self.video_worker.frame_signal.connect(self.update_camera_frame)
        self.video_worker.start()

    def _build_mode_panel(self, parent_layout):
        mode_group = QGroupBox("Active Control Mode")
        mode_layout = QVBoxLayout()
        self.lbl_mode = QLabel("LOADING...")
        self.lbl_mode.setAlignment(Qt.AlignCenter)
        self.lbl_mode.setStyleSheet("font-size: 24px; font-weight: bold; padding: 10px; border-radius: 5px;")
        mode_layout.addWidget(self.lbl_mode)
        mode_group.setLayout(mode_layout)
        parent_layout.addWidget(mode_group)

    def _build_status_panel(self, parent_layout):
        status_group = QGroupBox("System Status")
        status_layout = QHBoxLayout()
        self.lbl_gamepad = QLabel("Gamepad: DISCONNECTED")
        self.lbl_gamepad.setStyleSheet("color: red; font-weight: bold;")
        self.lbl_robot = QLabel("Robot Link: WAITING...")
        self.lbl_robot.setStyleSheet("color: orange; font-weight: bold;")
        status_layout.addWidget(self.lbl_gamepad)
        status_layout.addWidget(self.lbl_robot)
        status_group.setLayout(status_layout)
        parent_layout.addWidget(status_group)

    def _build_spatial_panel(self, parent_layout):
        spatial_group = QGroupBox("Task Space & IK Target")
        spatial_layout = QVBoxLayout()
        self.coord_labels = {}
        
        self.lbl_target = QLabel("TARGET: X: 0.0 | Y: 0.0 | Z: 0.0 | Yaw: 0.00 | Pitch: 0.00 | Roll: 0.00")
        self.lbl_target.setStyleSheet("font-family: 'Menlo', 'Courier New', monospace; color: #ff5555; font-weight: bold; background: #222; padding: 5px;")
        spatial_layout.addWidget(self.lbl_target)
        
        points = ["Shoulder", "Elbow", "Wrist", "Gripper (EE)"]
        for point in points:
            row = QHBoxLayout()
            name = QLabel(f"{point}:")
            name.setFixedWidth(100)
            val = QLabel("X: 0.0 | Y: 0.0 | Z: 0.0")
            val.setStyleSheet("font-family: 'Menlo', 'Courier New', monospace; color: cyan; font-weight: bold;")
            row.addWidget(name)
            row.addWidget(val)
            spatial_layout.addLayout(row)
            self.coord_labels[point] = val
            
        spatial_group.setLayout(spatial_layout)
        parent_layout.addWidget(spatial_group)
        
    def _build_telemetry_panel(self, parent_layout):
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
            value_label.setStyleSheet("font-family: 'Menlo', 'Courier New', monospace; font-weight: bold;")
            row_layout.addWidget(name_label)
            row_layout.addWidget(value_label)
            row_layout.addStretch()
            telemetry_layout.addLayout(row_layout)
            self.servo_labels.append(value_label)
        telemetry_group.setLayout(telemetry_layout)
        parent_layout.addWidget(telemetry_group)

    def _build_chassis_placeholder(self, parent_layout):
        chassis_group = QGroupBox("Chassis Stats (Placeholder)")
        chassis_layout = QVBoxLayout()
        lbl1 = QLabel("Battery: N/A")
        lbl2 = QLabel("Speed: 0.0 m/s")
        lbl3 = QLabel("Heading: 0°")
        chassis_layout.addWidget(lbl1)
        chassis_layout.addWidget(lbl2)
        chassis_layout.addWidget(lbl3)
        chassis_group.setLayout(chassis_layout)
        parent_layout.addWidget(chassis_group)

    def _build_camera_panel(self, parent_layout):
        camera_group = QGroupBox("Live Video Feed")
        camera_layout = QVBoxLayout()
        self.lbl_camera = QLabel("Waiting for video stream on port 5556...")
        self.lbl_camera.setAlignment(Qt.AlignCenter)
        self.lbl_camera.setStyleSheet("background-color: #000; color: #fff; font-weight: bold;")
        # Minimalna wysokość kamery, żeby nie zniknęła
        self.lbl_camera.setMinimumHeight(400)
        camera_layout.addWidget(self.lbl_camera)
        camera_group.setLayout(camera_layout)
        # Kamera zajmie 60% prawej kolumny
        parent_layout.addWidget(camera_group, 6)

    def _build_console_panel(self, parent_layout):
        console_group = QGroupBox("System Output / Logs")
        console_layout = QVBoxLayout()
        self.txt_console = QTextEdit()
        self.txt_console.setReadOnly(True)
        self.txt_console.setStyleSheet("background-color: #1e1e1e; color: #00ff00; font-family: 'Menlo', 'Courier New', monospace; font-size: 13px;")
        console_layout.addWidget(self.txt_console)
        console_group.setLayout(console_layout)
        # Konsola zajmie 40% prawej kolumny
        parent_layout.addWidget(console_group, 4)

    def update_camera_frame(self, frame_bytes):
        pixmap = QPixmap()
        pixmap.loadFromData(frame_bytes)
        # Skalowanie z zachowaniem proporcji do wymiarów okna
        self.lbl_camera.setPixmap(pixmap.scaled(self.lbl_camera.width(), self.lbl_camera.height(), Qt.KeepAspectRatio))

    def update_statuses(self, pad_ok, serial_ok):
        self.lbl_gamepad.setText("Gamepad: CONNECTED" if pad_ok else "Gamepad: DISCONNECTED")
        self.lbl_gamepad.setStyleSheet(f"color: {'green' if pad_ok else 'red'}; font-weight: bold;")
        self.lbl_robot.setText("Robot Link: ACTIVE" if serial_ok else "Robot Link: OFF")
        self.lbl_robot.setStyleSheet(f"color: {'green' if serial_ok else 'orange'}; font-weight: bold;")

    def update_target_ui(self, t, mode):
        colors = {
            "XYZ": ("#204a87", "#ffffff"),         
            "ORIENTATION": ("#c4a000", "#ffffff"), 
            "DRIVING": ("#cc0000", "#ffffff"),     
            "AUTONOMOUS": ("#4e9a06", "#ffffff")   
        }
        bg, fg = colors.get(mode, ("#555", "#fff"))
        self.lbl_mode.setText(f"[{mode}]")
        self.lbl_mode.setStyleSheet(f"font-size: 24px; font-weight: bold; padding: 10px; border-radius: 5px; background-color: {bg}; color: {fg};")
        
        if len(t) >= 6:
            self.lbl_target.setText(f"TARGET => X:{t[0]:.0f} | Y:{t[1]:.0f} | Z:{t[2]:.0f} | Yaw:{t[3]:.2f} | Pitch:{t[4]:.2f} | Roll:{t[5]:.2f}")

    def update_coords(self, coords_list):
        points = ["Shoulder", "Elbow", "Wrist", "Gripper (EE)"]
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
            scrollbar = self.txt_console.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

    def closeEvent(self, event):
        self.worker.stop()
        self.video_worker.stop()
        event.accept()