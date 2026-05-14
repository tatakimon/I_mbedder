"""
uart_feed.py — Window B
Live UART text feed from COM5 at 115200 baud.
Run in its own terminal:
    python C:\\Users\\kerem\\Documents\\ImbedderNewTrial_MAI\\uart_feed.py
"""

import serial
import time
import os
import sys
import json

# ---------------------------------------------------------------------------
# Circular buffer log helper — max 50 lines, overwrites oldest
# ---------------------------------------------------------------------------
MAX_LOG_LINES = 50


def append_log(filepath, line):
    """Write line to filepath, keep only the newest MAX_LOG_LINES."""
    lines = []
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                lines = f.read().splitlines()
        except Exception:
            lines = []
    lines.append(line.rstrip())
    lines = lines[-MAX_LOG_LINES:]
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
COM_PORT    = "COM5"
UART_BAUD   = 115200
STATUS_FILE = "C:/Users/kerem/Documents/ImbedderNewTrial_MAI/status.json"
LOG_FILE    = "C:/Users/kerem/Documents/ImbedderNewTrial_MAI/uart_log.txt"


def write_status(key, value):
    try:
        d = json.load(open(STATUS_FILE)) if os.path.exists(STATUS_FILE) else {}
        d[key] = value
        json.dump(d, open(STATUS_FILE, "w"), indent=2)
    except Exception:
        pass


def run():
    os.system("title UART Feed")
    print("[UART FEED] Opening COM5 at 115200 baud...")
    try:
        ser = serial.Serial(COM_PORT, UART_BAUD, timeout=5)
        time.sleep(1)  # wait for board to boot and print first line
        print(f"[UART FEED] Listening on {COM_PORT} {UART_BAUD} baud. Ctrl+C to stop.\n")
    except serial.SerialException as e:
        print(f"[UART FEED] ERROR: Cannot open {COM_PORT} — {e}")
        print("Is TeraTerm or another terminal open on this port? Close it first.")
        sys.exit(1)

    while True:
        try:
            data = ser.read(200)
            if data:
                text = data.decode("ascii", errors="replace")
                print(text, end="", flush=True)
                for line in text.splitlines(keepends=True):
                    append_log(LOG_FILE, line)
                # Strip newlines for status.json display
                clean = text.replace("\r", " ").replace("\n", " ").strip()
                if clean:
                    write_status("uart_last", clean[:80])
        except serial.SerialException:
            print("[UART FEED] Port disconnected.")
            break
        except KeyboardInterrupt:
            print("\n[UART FEED] Stopped.")
            break


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\n[UART FEED] Stopped.")
        sys.exit(0)