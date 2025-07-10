# 呼吸频率监测系统 （峰值检测 + 生理参数 + 心率波形）

本项目基于 PyQt5 + pyqtgraph 实现了一款支持 **TCP Socket 通信、ADC 电压监测、呼吸频率检测、MKS 生理参数解析**（心率、血氧）、**心率波形绘图** 的多功能健康监测软件。

## 📦 功能概述

- 📡 **TCP 通信连接**：支持设定 IP 与端口，监听接收传感器数据。
- 🔋 **电压曲线绘制**：实时显示 ADC 通道电压值（CH1）。
- 📈 **呼吸频率计算**：基于峰值检测自动统计每分钟呼吸次数。
- ❤️ **心率/血氧参数提取**：自动解析 MKS 模块输出中的 `HR` 与 `SpO2` 字段。
- 🧠 **心率波形绘图**：解析 `AC=[...]` 心率波形数据并动态显示。
- 🧼 **清除数据与断开功能**：支持一键清除曲线、波形和历史信息。

## 🧩 软件架构

- `main.py`: 主程序入口，构建 UI 与逻辑。
- `VoltageMonitor(QWidget)`: 主界面类，集成各功能模块。
- 信号槽机制：`data_signal`、`peak_count_signal`、`pulse_signal` 实现跨线程数据更新。
- `receive_data()`: 监听 TCP，解析 `V0=`, `AC=[]`, `HR=`, `SpO2=` 等关键字段。
- `update_ui()` 与 `update_pulse_plot()`：动态更新电压曲线与心率波形。

## 📊 性能指标（节选）

| 指标类型                 | 参数值                        |
|-------------------------|-------------------------------|
| 呼吸采样频率             |          100 Hz               |
| 通信方式                 |   TCP Socket，端口可配置       |
| 呼吸频率误差             |    ±2 次/min（基于峰值检测）    |
| 血氧测量精度             |    ±2%（基于 MKS 传感器）       |
| 系统功耗                 |         小于 5W                |
| ADC 分辨率               |           12 位                |
| 自动电阻切换             |    10kΩ～10MΩ 共五档自动切换     |

详见文档内 `表 1. 性能指标`。

## 🚀 快速运行
上位机（GUI）：
```bash
# 安装依赖
pip install pyqt5 pyqtgraph

# 启动软件
python main.py
下位机（开发板）：
# Step 1: 交叉编译（LoongArch）
进入文件件，打开终端
vim Makefile
内容如下：
CC=loongarch64-linux-gnu-gcc
CFLAGS=-Wall -Iinclude

SRCS=$(wildcard src/*.c)
OBJS=$(patsubst src/%.c,build/%.o,$(SRCS))
TARGET=main

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CC) $(CFLAGS) -o $@ $^ -lm

build/%.o: src/%.c
	@mkdir -p build
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -rf build $(TARGET)
进行编译：
make

# Step 2: 上传至开发板
scp main /home/loongson@开发板IP:/home/loongson/

# Step 3: SSH 登录并运行
ssh loongson@开发板IP
chmod +x main//赋予权限
./main
