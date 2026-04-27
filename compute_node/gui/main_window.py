from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QTextEdit, QGridLayout
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from gui.network_worker import NetworkWorker, VideoWorker, TelemetryWorker

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UGV02 - Compute Node Command Center")
        self.resize(1200, 850) 
        self.setStyleSheet("font-size: 13px; font-family: 'Menlo', 'Courier New', monospace;")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QHBoxLayout(central_widget)
        
        self.left_column = QVBoxLayout()
        self.right_column = QVBoxLayout()
        
        self._build_mode_panel(self.left_column)
        self._build_system_status_panel(self.left_column)
        self._build_spatial_panel(self.left_column) 
        self._build_servo_status_panel(self.left_column)
        self._build_chassis_stats(self.left_column)
        self.left_column.addStretch()

        self._build_camera_panel(self.right_column)
        self._build_console_panel(self.right_column)

        self.main_layout.addLayout(self.left_column, 1)
        self.main_layout.addLayout(self.right_column, 2)

        self.worker = NetworkWorker()
        self.worker.status_signal.connect(self.update_pad_status)
        self.worker.start()

        self.telemetry_worker = TelemetryWorker()
        self.telemetry_worker.feedback_signal.connect(self.process_telemetry)
        self.telemetry_worker.start()

        self.video_worker = VideoWorker()
        self.video_worker.frame_signal.connect(self.update_camera_frame)
        self.video_worker.start()

    def _build_mode_panel(self, parent):
        group = QGroupBox("Active Control Mode")
        layout = QVBoxLayout()
        self.lbl_mode = QLabel("[WAITING FOR DATA]")
        self.lbl_mode.setAlignment(Qt.AlignCenter)
        self.lbl_mode.setStyleSheet("font-size: 22px; font-weight: bold; padding: 5px; border-radius: 5px; background: #333;")
        layout.addWidget(self.lbl_mode)
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
        group = QGroupBox("Task Space & IK Target")
        layout = QVBoxLayout()
        self.coord_labels = {}
        
        self.lbl_target = QLabel("TARGET: X:0 Y:0 Z:0 | Yaw:0 Pitch:0 Roll:0")
        self.lbl_target.setStyleSheet("color: #ff5555; font-weight: bold; background: #222; padding: 4px;")
        layout.addWidget(self.lbl_target)
        
        points = ["Shoulder", "Elbow", "Wrist", "Gripper"]
        for point in points:
            row = QHBoxLayout()
            name = QLabel(f"{point}:")
            name.setFixedWidth(80)
            val = QLabel("X: 0.0 | Y: 0.0 | Z: 0.0")
            val.setStyleSheet("color: cyan; font-weight: bold;")
            row.addWidget(name)
            row.addWidget(val)
            layout.addLayout(row)
            self.coord_labels[point] = val
        group.setLayout(layout)
        parent.addWidget(group)
        
    def _build_servo_status_panel(self, parent):
        group = QGroupBox("Servo Status Dashboard")
        layout = QGridLayout()
        
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
        group = QGroupBox("Chassis Stats")
        layout = QHBoxLayout()
        self.lbl_battery = QLabel("Battery: WAIT")
        self.lbl_battery.setStyleSheet("font-size: 16px; font-weight: bold; color: yellow;")
        layout.addWidget(self.lbl_battery)
        group.setLayout(layout)
        parent.addWidget(group)

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

    def update_camera_frame(self, frame_bytes):
        pixmap = QPixmap()
        pixmap.loadFromData(frame_bytes)
        self.lbl_camera.setPixmap(pixmap.scaled(self.lbl_camera.width(), self.lbl_camera.height(), Qt.KeepAspectRatio))

    def process_telemetry(self, data):
        # 1. Update Mode
        mode = data.get("mode", "UNKNOWN")
        colors = {"XYZ": "#204a87", "RPY": "#c4a000", "DRIVING": "#cc0000", "AUTONOMOUS": "#4e9a06"} 
        self.lbl_mode.setText(f"[{mode}]")
        self.lbl_mode.setStyleSheet(f"font-size: 22px; font-weight: bold; padding: 5px; border-radius: 5px; background-color: {colors.get(mode, '#555')}; color: #fff;")
        
        t = data.get("target", [0,0,0,0,0,0])
        if len(t) >= 6:
            self.lbl_target.setText(f"TARGET: X:{t[0]:.0f} Y:{t[1]:.0f} Z:{t[2]:.0f} | Roll:{t[5]:.2f} Pitch:{t[4]:.2f} Yaw:{t[3]:.2f}")

        # 2. System Status
        self.status_labels["node"].setText(f"Controller: {data.get('node_status')}")
        self.status_labels["node"].setStyleSheet("color: #4e9a06; font-weight: bold;")
        
        arm_s = data.get('arm_status', 'WAIT')
        self.status_labels["arm"].setText(f"Arm: {arm_s}")
        self.status_labels["arm"].setStyleSheet(f"color: {'cyan' if 'MOVING' in arm_s else '#4e9a06' if arm_s == 'ACTIVE' else 'gray'}; font-weight: bold;")
        
        chas_s = data.get('chassis_status', 'WAIT')
        self.status_labels["chassis"].setText(f"Chassis: {chas_s}")
        self.status_labels["chassis"].setStyleSheet(f"color: {'cyan' if chas_s == 'MOVING' else '#4e9a06' if chas_s == 'ACTIVE' else 'gray'}; font-weight: bold;")
        # 3. Spatial Coords
        coords = data.get("coords", [])
        if len(coords) >= 4:
            pts = ["Shoulder", "Elbow", "Wrist", "Gripper"]
            for i, pt in enumerate(pts):
                self.coord_labels[pt].setText(f"X: {coords[i][0]:>5.1f} | Y: {coords[i][1]:>5.1f} | Z: {coords[i][2]:>5.1f}")

        # 4. Dashboard z danymi o serwach (Uproszczone Statusy)
        servos = data.get("servos", [])
        if len(servos) == len(self.servo_data):
            for i, s_data in enumerate(servos):
                self.servo_data[i]["pos"].setText(str(s_data["pos"]))
                self.servo_data[i]["temp"].setText(f"{s_data['temp']} °C" if s_data['temp'] != '--' else "-- °C")
                self.servo_data[i]["vol"].setText(f"{s_data['volt']} V" if s_data['volt'] != '--' else "-- V")
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

        # 5. Bateria Podwozia
        chas_data = data.get("chassis_data", {})
        volts = chas_data.get("voltage", 0.0)
        self.lbl_battery.setText(f"Battery: {volts:.2f} V")
        self.lbl_battery.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {'red' if volts > 0 and volts < 10.5 else '#4e9a06'};")

        # 6. Czyste Logi
        for log in data.get("logs", []):
            self.txt_console.append(log)
            sb = self.txt_console.verticalScrollBar()
            sb.setValue(sb.maximum())

    def closeEvent(self, event):
        self.worker.stop()
        self.telemetry_worker.stop()
        self.video_worker.stop()
        event.accept()