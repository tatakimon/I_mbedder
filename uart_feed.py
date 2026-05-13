"""
uart_feed.py — Window B (TeraTerm alternative)
Reads UART via LA decode (sigrok-cli) and prints decoded text live.
No box-drawing, no formatting — just the raw feed like TeraTerm.

Run in its own terminal:
    python C:\\Users\\kerem\\Documents\\ImbedderNewTrial_MAI\\uart_feed.py

Press Ctrl+C to stop.
"""

import subprocess
import time
import re
import os
import sys
import json

SIGROK_CLI   = "C:/Program Files/sigrok/sigrok-cli/sigrok-cli.exe"
STATUS_FILE  = "C:/Users/kerem/Documents/ImbedderNewTrial_MAI/status.json"
SAMPLERATE   = "1m"
CAPTURE_TIME = "500ms"
UART_BAUD    = 115200


def write_status(key, value):
    try:
        d = json.load(open(STATUS_FILE)) if os.path.exists(STATUS_FILE) else {}
        d[key] = value
        json.dump(d, open(STATUS_FILE, "w"), indent=2)
    except Exception:
        pass


def decode_lines(stdout_text):
    """Convert '35-105 uart-1: 54' lines to clean ASCII string."""
    vals = []
    for line in stdout_text.splitlines():
        m = re.search(r"\d+-\d+ uart-1:\s*([0-9A-Fa-f]{2})", line)
        if m:
            v = int(m.group(1), 16)
            vals.append(v)
    text = "".join(chr(v) if 32 <= v < 127 else "." for v in vals)
    return vals, text


def run():
    os.system("title UART Feed")
    print("[UART FEED] Starting... make sure firmware is running.")
    print("[UART FEED] Reading D1 (LA CH1) at 115200 baud. Ctrl+C to stop.\n")

    frame_count = 0
    while True:
        cmd = [
            SIGROK_CLI, "--driver", "fx2lafw",
            "--config", f"samplerate={SAMPLERATE}",
            "--time",   CAPTURE_TIME,
            "--triggers", "D1=f",
            "-P", f"uart:baudrate={UART_BAUD}:rx=D1",
            "-A", "uart=rx-data",
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
            _, text = decode_lines(result.stdout)
            if text.strip():
                frame_count += 1
                print(text, end="", flush=True)
                write_status("uart_last", text[:80].replace("\r", " ").replace("\n", " "))
        except subprocess.TimeoutExpired:
            print("[feed] timeout waiting for data... is the firmware running?")
        except Exception as e:
            print(f"[feed] error: {e}")
        time.sleep(0.5)


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\n[UART FEED] Stopped.")
        sys.exit(0)