import sys
import serial
import serial.tools.list_ports
import threading
import time

def list_ports():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        print(f"Port: {port.device}, Description: {port.description}")

def read_from_port(ser):
    while True:
        if ser.in_waiting > 0:
            data = ser.read(ser.in_waiting)
            try:
                print("Received:", data.decode('utf-8', errors='replace'))
            except Exception as e:
                print("Decode error:", e)
        time.sleep(0.1)

def main():
    list_ports()
    port_name = input("Enter the serial port to open (e.g., COM3): ").strip()
    baud_rate = input("Enter baud rate (e.g., 115200): ").strip()
    try:
        baud_rate = int(baud_rate)
    except ValueError:
        print("Invalid baud rate, using 115200")
        baud_rate = 115200

    try:
        ser = serial.Serial(port=port_name, baudrate=baud_rate, timeout=0.1)
        print(f"Opened port {port_name} at {baud_rate} baud.")
    except Exception as e:
        print(f"Failed to open port: {e}")
        sys.exit(1)

    read_thread = threading.Thread(target=read_from_port, args=(ser,), daemon=True)
    read_thread.start()

    print("Start receiving data. Press Ctrl+C to exit.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Exiting...")
        ser.close()
        sys.exit(0)

if __name__ == "__main__":
    main()
