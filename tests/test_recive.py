import serial
import time
import math
import struct
import sys

# --- 1. 协议和串口配置 ---
# 你可以根据实际情况修改这些配置
SERIAL_PORT = 'COM2'
BAUD_RATE = 9600  # 波特率，必须与接收设备一致
HEAD = 0xAB       # 帧头
S_ADDR = 0x10     # 源地址 (例如，PC的地址)
D_ADDR = 0x20     # 目标地址 (接收设备的地址)

# 定义一个功能码，用于表示本次传输的是sin(t)数据
# 接收方可以根据这个ID来解析数据内容
FUNC_ID_SINE_WAVE = 0xF1

def calculate_custom_checksums(data_bytes: bytes) -> tuple[int, int]:
    """
    根据协议文档中的C代码实现和校验(sumcheck)与附加校验(addcheck)。
    
    :param data_bytes: 包含从帧头到数据内容的所有字节
    :return: (sum_check, add_check) 元组
    """
    sum_check = 0
    add_check = 0
    for byte in data_bytes:
        # C语言中的 uint8_t 会自动处理溢出，Python中需要用 & 0xFF 来模拟
        sum_check = (sum_check + byte) & 0xFF 
        add_check = (add_check + sum_check) & 0xFF
    
    return sum_check, add_check

def assemble_frame(function_id: int, payload_data: bytes) -> bytes:
    """
    根据协议组装完整的数据帧。
    
    :param function_id: 功能码
    :param payload_data: 已经打包好的数据内容字节
    :return: 完整的、可直接发送的帧字节
    """
    # --- 组装需要计算校验和的部分 ---
    
    # 1. 帧头 (1 Byte)
    head_byte = HEAD.to_bytes(1, 'big')
    
    # 2. 源地址 & 目标地址 (1 + 1 = 2 Bytes)
    saddr_byte = S_ADDR.to_bytes(1, 'big')
    daddr_byte = D_ADDR.to_bytes(1, 'big')
    
    # 3. 功能码 (1 Byte)
    id_byte = function_id.to_bytes(1, 'big')
    
    # 4. 数据长度 (2 Bytes, 小端序)
    # 这是关键修改点，确保长度为2字节
    payload_len = len(payload_data)
    len_bytes = struct.pack('<H', payload_len) # '<H' = 小端序, 无符号短整型 (2 bytes)
    
    # 5. 数据内容 (N Bytes)
    # payload_data 已作为参数传入
    
    # 将所有部分连接起来，用于计算校验和
    frame_part_for_checksum = head_byte + saddr_byte + daddr_byte + id_byte + len_bytes + payload_data
    
    # --- 计算并附加校验和 ---
    
    # 6. 和校验 & 附加校验 (1 + 1 = 2 Bytes)
    sc_val, ac_val = calculate_custom_checksums(frame_part_for_checksum)
    sc_byte = sc_val.to_bytes(1, 'big')
    ac_byte = ac_val.to_bytes(1, 'big')
    
    # --- 生成最终数据帧 ---
    final_frame = frame_part_for_checksum + sc_byte + ac_byte
    
    return final_frame

def main():
    """
    主执行函数
    """
    print(f"尝试打开串口 {SERIAL_PORT}...")
    
    try:
        # 初始化串口
        ser = serial.Serial(
            port=SERIAL_PORT,
            baudrate=BAUD_RATE,
            timeout=1  # 设置写入超时
        )
        print(f"串口 {SERIAL_PORT} 打开成功，波特率 {BAUD_RATE}。")
    except serial.SerialException as e:
        print(f"错误：无法打开串口 {SERIAL_PORT}。")
        print(f"  > {e}")
        print("请检查串口号是否正确，或设备是否已被其他程序占用。")
        sys.exit(1) # 退出程序

    # 初始化时间变量 t
    t = 0
    
    print("\n按 Ctrl+C 停止发送。")
    
    try:
        while True:
            # 1. 计算 sin(t) 值
            sin_value_float = math.sin(t)
            
            # 2. 将浮点数映射并转换为一个16位有符号整数 (short)
            # 我们将 [-1.0, 1.0] 乘以 10000，映射到 [-10000, 10000] 范围
            scaled_value = int(sin_value_float * 10000)
            
            # 3. 将整数打包成2个字节的数据内容 (小端序)
            # '<h' = 小端序, 有符号短整型 (2 bytes)
            payload = struct.pack('<h', scaled_value)
            
            # 4. 使用功能码和数据内容组装完整数据帧
            frame_to_send = assemble_frame(FUNC_ID_SINE_WAVE, payload)
            
            # 5. 发送数据帧
            ser.write(frame_to_send)
            
            # 6. 在控制台打印发送信息，便于调试
            # .hex(' ') 会将字节串格式化为带空格的十六进制字符串，如 "AB 10 20 ..."
            print(f"t={t:6.2f} | sin(t)={sin_value_float:8.4f} | Sent Int: {scaled_value:6d} | Frame: {frame_to_send.hex(' ').upper()}")
            
            # 7. 更新时间和等待
            t += 0.1
            time.sleep(0.1) # 每0.1秒发送一次

    except KeyboardInterrupt:
        print("\n程序被用户中断。")
    except Exception as e:
        print(f"\n发生未知错误: {e}")
    finally:
        # 确保在程序退出时关闭串口
        if ser.is_open:
            ser.close()
            print(f"串口 {SERIAL_PORT} 已关闭。")

if __name__ == '__main__':
    main()