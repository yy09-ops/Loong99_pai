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
    data_signal = pyqtSignal(float, str)
    peak_count_signal = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("呼吸频率监测（峰值检测 + 生理参数）")
        self.setGeometry(100, 100, 800, 600)

        # 网络与控制
        self.server_socket = None
        self.client_socket = None
        self.running = False
        self.conn_thread = None

        # 数据处理
        self.data_x = deque(maxlen=100)
        self.data_ch1 = deque(maxlen=100)
        self.peak_times = deque()
        self.cur_index = 0
        self.is_updating_frequency = False

        # 窗口部件
        self.ip_input = QLineEdit("0.0.0.0")
        self.port_input = QLineEdit("8080")
        self.connect_button = QPushButton("连接")
        self.connect_button.clicked.connect(self.start_listen)

        self.voltage1_label = QLabel("CH1: 0.0 V")
        self.predict_label = QLabel("呼吸频率：0 次/分钟")

        # MKS 参数显示标签
        self.hr_label = QLabel("心率：-- bpm")
        self.spo2_label = QLabel("血氧：-- %")
        self.bp_label = QLabel("血压：-- / -- mmHg")
        self.fatigue_label = QLabel("疲劳：--")
        self.micro_label = QLabel("微循环：--")

        self.clear_button = QPushButton("清除数据")
        self.disconnect_button = QPushButton("断开连接")
        self.disconnect_button.clicked.connect(self.disconnect)
        self.clear_button.clicked.connect(self.clear_data)

        self.plot_widget = PlotWidget(title="CH1 ADC电压值")
        self.plot_widget.setLabel('left', '电压', units='V')
        self.plot_widget.setLabel('bottom', '采样点')
        self.plot_widget.addLegend()
        self.line1 = self.plot_widget.plot(pen='r', name='CH1')

        self.receive_text = QTextEdit()
        self.receive_text.setReadOnly(True)

        self.init_ui()

        self.data_signal.connect(self.update_ui)
        self.peak_count_signal.connect(self.update_breathing_frequency)

        self.measure_timer = QTimer(self)
        self.measure_timer.timeout.connect(self.update_breathing_frequency)
        self.measure_timer.start(1000)

    def init_ui(self):
        net_layout = QGridLayout()
        net_layout.addWidget(QLabel("主机地址"), 0, 0)
        net_layout.addWidget(self.ip_input, 0, 1)
        net_layout.addWidget(QLabel("端口"), 1, 0)
        net_layout.addWidget(self.port_input, 1, 1)
        net_layout.addWidget(self.connect_button, 2, 0, 1, 2)

        voltage_box = QVBoxLayout()
        voltage_box.addWidget(self.voltage1_label)
        voltage_box.addWidget(self.predict_label)
        voltage_box.addWidget(self.hr_label)
        voltage_box.addWidget(self.spo2_label)
        voltage_box.addWidget(self.bp_label)
        voltage_box.addWidget(self.fatigue_label)
        voltage_box.addWidget(self.micro_label)
        voltage_box.addWidget(self.clear_button)
        voltage_box.addWidget(self.disconnect_button)

        left_panel = QVBoxLayout()
        left_panel.addLayout(net_layout)
        left_panel.addLayout(voltage_box)

        tabs = QTabWidget()
        tabs.addTab(self.receive_text, "数据接收")
        tabs.addTab(self.plot_widget, "波形曲线")

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
            self.running = True
            threading.Thread(target=self.receive_data, daemon=True).start()
        except Exception as e:
            self.receive_text.append(f"❌ 接收失败：{e}")

    def receive_data(self):
        smooth_buf = deque(maxlen=5)
        peak_buf = deque(maxlen=5)

        while self.running:
            try:
                data = self.client_socket.recv(2048).decode().strip()
                if not data:
                    continue
                self.data_signal.emit(0, data)

                if data.startswith("V0="):
                    try:
                        v0 = float(data.split("=")[1].split()[0])
                        smooth_buf.append(v0)
                        v0_avg = sum(smooth_buf) / len(smooth_buf)

                        peak_buf.append(v0_avg)
                        if len(peak_buf) == 5:
                            mid = 2
                            if (peak_buf[mid] > 0.5 and
                                peak_buf[mid] > peak_buf[mid - 1] and
                                peak_buf[mid] > peak_buf[mid + 1]):
                                now = time.time()
                                if len(self.peak_times) == 0 or (now - self.peak_times[-1]) > 0.3:
                                    self.peak_times.append(now)
                                    self.update_breathing_frequency()

                        self.data_signal.emit(v0_avg, "")
                    except Exception as e:
                        self.data_signal.emit(0, f"⚠️ 电压解析错误：{e}")

                elif data.startswith("AC=["):
                    try:
                        # 示例：AC=[...], HR=85, SpO2=98, Micro=123, SysBP=120, DiaBP=75, Fatigue=3
                        kvs = dict()
                        fields = data.split(",")
                        for field in fields:
                            if "=" in field:
                                k, v = field.strip().split("=")
                                kvs[k.strip()] = v.strip()
                        self.hr_label.setText(f"心率：{kvs.get('HR', '--')} bpm")
                        self.spo2_label.setText(f"血氧：{kvs.get('SpO2', '--')} %")
                        self.micro_label.setText(f"微循环：{kvs.get('Micro', '--')}")
                        self.bp_label.setText(f"血压：{kvs.get('SysBP', '--')} / {kvs.get('DiaBP', '--')} mmHg")
                        self.fatigue_label.setText(f"疲劳：{kvs.get('Fatigue', '--')}")
                    except Exception as e:
                        self.data_signal.emit(0, f"⚠️ 生理参数解析错误：{e}")

            except Exception as e:
                self.data_signal.emit(0, f"⚠️ 接收异常：{e}")
                break

    def update_breathing_frequency(self):
        if self.is_updating_frequency:
            return
        self.is_updating_frequency = True

        if len(self.peak_times) < 2:
            self.is_updating_frequency = False
            return

        intervals = [self.peak_times[i] - self.peak_times[i - 1] for i in range(1, len(self.peak_times))]
        avg_interval = sum(intervals) / len(intervals)
        freq = int(60 / avg_interval)
        self.peak_count_signal.emit(freq)
        self.predict_label.setText(f"呼吸频率：{freq} 次/分钟")

        self.is_updating_frequency = False

    def update_ui(self, voltage, raw_text):
        if raw_text:
            self.receive_text.append(raw_text)

        if voltage > 0:
            self.voltage1_label.setText(f"CH1: {voltage:.1f} V")
            self.data_x.append(self.cur_index)
            self.data_ch1.append(voltage)
            self.line1.setData(self.data_x, self.data_ch1)
            self.cur_index += 1

    def clear_data(self):
        self.data_x.clear()
        self.data_ch1.clear()
        self.cur_index = 0
        self.peak_times.clear()
        self.line1.setData([], [])
        self.receive_text.clear()
        self.voltage1_label.setText("CH1: 0.0 V")
        self.predict_label.setText("呼吸频率：0 次/分钟")

    def disconnect(self):
        self.running = False
        try:
            if self.client_socket:
                self.client_socket.close()
                self.client_socket = None
            if self.server_socket:
                self.server_socket.close()
                self.server_socket = None
            self.receive_text.append("🔌 已断开连接")
        except Exception as e:
            self.receive_text.append(f"⚠️ 断开连接失败：{e}")


def main():
    app = QApplication(sys.argv)
    window = VoltageMonitor()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
