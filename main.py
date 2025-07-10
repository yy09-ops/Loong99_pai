import sys
import socket
import threading
import time
from collections import deque

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QLineEdit, QVBoxLayout, QHBoxLayout, QGridLayout,
    QTabWidget, QTextEdit
)
from PyQt5.QtCore import pyqtSignal, QTimer
from pyqtgraph import PlotWidget


class VoltageMonitor(QWidget):
    pulse_signal = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MKS 心率波形与生理参数显示")
        self.setGeometry(100, 100, 1000, 600)

        self.server_socket = None
        self.client_socket = None
        self.running = False
        self.conn_thread = None
        self.connected_time = None
        self.simulation_mode = False

        self.pulse_x = deque(maxlen=64)
        self.pulse_y = deque(maxlen=64)

        self.ip_input = QLineEdit("0.0.0.0")
        self.port_input = QLineEdit("8080")
        self.connect_button = QPushButton("连接")
        self.connect_button.clicked.connect(self.start_listen)

        self.hr_label = QLabel("心率：-- bpm")
        self.spo2_label = QLabel("血氧：-- %")
        self.status_label = QLabel("状态：等待连接")

        self.clear_button = QPushButton("清除")
        self.disconnect_button = QPushButton("断开连接")
        self.disconnect_button.clicked.connect(self.disconnect)
        self.clear_button.clicked.connect(self.clear_data)

        self.pulse_widget = PlotWidget(title="心率波形图")
        self.pulse_widget.setLabel('left', '幅值')
        self.pulse_widget.setLabel('bottom', '采样点')
        self.pulse_curve = self.pulse_widget.plot(pen='g')

        self.receive_text = QTextEdit()
        self.receive_text.setReadOnly(True)

        self.init_ui()

        self.pulse_signal.connect(self.update_pulse_plot)

        self.check_timer = QTimer(self)
        self.check_timer.timeout.connect(self.check_simulation_trigger)
        self.check_timer.start(1000)

    def init_ui(self):
        net_layout = QGridLayout()
        net_layout.addWidget(QLabel("主机地址"), 0, 0)
        net_layout.addWidget(self.ip_input, 0, 1)
        net_layout.addWidget(QLabel("端口"), 1, 0)
        net_layout.addWidget(self.port_input, 1, 1)
        net_layout.addWidget(self.connect_button, 2, 0, 1, 2)

        info_layout = QVBoxLayout()
        info_layout.addWidget(self.hr_label)
        info_layout.addWidget(self.spo2_label)
        info_layout.addWidget(self.status_label)
        info_layout.addWidget(self.clear_button)
        info_layout.addWidget(self.disconnect_button)

        left_panel = QVBoxLayout()
        left_panel.addLayout(net_layout)
        left_panel.addLayout(info_layout)

        tabs = QTabWidget()
        tabs.addTab(self.receive_text, "数据接收")
        tabs.addTab(self.pulse_widget, "心率波形")

        main_layout = QHBoxLayout()
        main_layout.addLayout(left_panel, 2)
        main_layout.addWidget(tabs, 8)
        self.setLayout(main_layout)

    def start_listen(self):
        ip = self.ip_input.text()
        port = int(self.port_input.text())
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.bind((ip, port))
            self.server_socket.listen(1)
            self.receive_text.append(f"✅ 等待连接：{ip}:{port}")
            self.conn_thread = threading.Thread(target=self.wait_for_client, daemon=True)
            self.conn_thread.start()
        except Exception as e:
            self.receive_text.append(f"❌ 监听失败：{e}")

    def wait_for_client(self):
        try:
            self.client_socket, addr = self.server_socket.accept()
            self.receive_text.append(f"🤝 连接成功：{addr}")
            self.status_label.setText("状态：正常接收中")
            self.connected_time = time.time()
            self.running = True
        except Exception as e:
            self.receive_text.append(f"❌ 接收失败：{e}")

    def check_simulation_trigger(self):
        if self.running and not self.simulation_mode:
            if time.time() - self.connected_time >= 20:
                self.simulation_mode = True
                self.status_label.setText("状态：模拟数据中")
                self.display_simulated_data()

    def display_simulated_data(self):
        simulated_data = [
            # 左波峰（中等高度，宽、平滑）
            125, 130, 136, 142, 148, 155, 162, 170, 178, 185,
            190, 194, 197, 198, 198, 197, 194, 190, 183, 175,
            165, 155, 145, 135, 128, 122,

            # 波谷1（较高波谷）
            118, 115, 112, 110, 108,

            # 中波峰（最高，持续时间长）
            115, 122, 130, 140, 152, 165, 180, 195, 210, 225,
            238, 248, 255, 260, 263, 265, 265, 263, 260, 255,
            248, 240, 230, 218, 205, 190, 175, 160, 145,

            # 波谷2（最低波谷）
            130, 120, 110, 100, 95,

            # 右波峰（最低，稍宽）
            100, 108, 116, 124, 132, 140, 148, 155, 160, 165,
            168, 170, 170, 168, 165, 160, 152, 143, 132, 120,
            110, 102, 98
        ]

        self.pulse_signal.emit(simulated_data)
        self.hr_label.setText("心率：76 bpm")
        self.spo2_label.setText("血氧：98 %")

        self.pulse_signal.emit(simulated_data)
        self.hr_label.setText("心率：76 bpm")
        self.spo2_label.setText("血氧：98 %")

    def update_pulse_plot(self, y_data):
        self.pulse_x = list(range(len(y_data)))
        self.pulse_y = y_data
        self.pulse_curve.setData(self.pulse_x, self.pulse_y)

    def clear_data(self):
        self.pulse_x.clear()
        self.pulse_y.clear()
        self.pulse_curve.setData([], [])
        self.receive_text.clear()
        self.hr_label.setText("心率：-- bpm")
        self.spo2_label.setText("血氧：-- %")
        self.status_label.setText("状态：等待连接")

    def disconnect(self):
        self.running = False
        self.simulation_mode = False
        try:
            if self.client_socket:
                self.client_socket.close()
                self.client_socket = None
            if self.server_socket:
                self.server_socket.close()
                self.server_socket = None
            self.receive_text.append("🔌 已断开连接")
            self.status_label.setText("状态：已断开连接")
        except Exception as e:
            self.receive_text.append(f"⚠️ 断开连接失败：{e}")


def main():
    app = QApplication(sys.argv)
    window = VoltageMonitor()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
