import serial
import time

def main():
    try:
        ser = serial.Serial('COM1', 9600, timeout=1)
        print("Opened port COM1 at 9600 baud.")
    except Exception as e:
        print(f"Failed to open port: {e}")
        return

    try:
        while True:
            ser.write(b'\xff')
            print("Sent: 0xFF")
            time.sleep(1)
    except KeyboardInterrupt:
        print("Exiting...")
        ser.close()

if __name__ == "__main__":
    main()
