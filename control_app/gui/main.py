import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel
from PySide6.QtCore import Qt

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # main window configuration
        self.setWindowTitle("UGV02 - Command Center")
        self.setFixedSize(800, 600)

        # set up vertical layout
        layout = QVBoxLayout() 

        # status label
        self.status_label = QLabel("Status: Waiting for RPi5 connection...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        # connect button
        self.btn_connect = QPushButton("Initialize System")
        self.btn_connect.clicked.connect(self.on_connect_clicked)
        layout.addWidget(self.btn_connect)

        # wrap layout in a central widget
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    # slot triggered on button click
    def on_connect_clicked(self):
        self.status_label.setText("Status: Initializing UDP protocol and vision...")
        self.btn_connect.setEnabled(False) # prevent multiple clicks
        print("[INFO] Connection thread will be spawned here")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
