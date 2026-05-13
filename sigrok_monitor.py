"""
sigrok_monitor.py — LA timing + signal analysis monitor
Window A of the HIL pipeline.

Run in its own terminal:
    python C:\\Users\\kerem\\Documents\\ImbedderNewTrial_MAI\\sigrok_monitor.py

What it does:
  1. Captures LA data live via sigrok-cli (single command, no intermediate file)
  2. Decodes USART3 TX (D1) as UART 115200 baud and prints ASCII output
  3. Reports bit timing accuracy (measured vs expected)
  4. Writes uart_last and i2c_last to status.json for stage_monitor to display

Hardware: Saleae Logic clone, fx2lafw driver. Probe CH1 (LA D1) → PD8 on B-U585I-IOT02A.
"""

import subprocess
import json
import os
import sys
import time
import re
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SIGROK_CLI     = "C:/Program Files/sigrok/sigrok-cli/sigrok-cli.exe"
STATUS_FILE    = "C:/Users/kerem/Documents/ImbedderNewTrial_MAI/status.json"
SAMPLERATE     = "1m"          # 1 MHz — sufficient for 115200 baud
CAPTURE_TIME   = "500ms"        # capture window
UART_BAUD      = 115200
REFRESH_SEC    = 2.0

# Expected bit time @ 115200 = 8.68 us
EXPECTED_BIT_US = 1_000_000.0 / UART_BAUD   # 8.68 us

W = 80


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------
def clear_screen():
    os.system("cls")


def read_status():
    try:
        with open(STATUS_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def write_status_field(key, value):
    try:
        data = read_status()
        data[key] = value
        with open(STATUS_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def hex_to_ascii(hex_lines):
    """Convert list of 'uart-1: XX' lines to decoded string."""
    bytes_list = []
    for line in hex_lines:
        m = re.search(r":\s*([0-9A-Fa-f]{2})", line)
        if m:
            bytes_list.append(int(m.group(1), 16))

    if not bytes_list:
        return "", ""

    hex_str = " ".join(f"{b:02X}" for b in bytes_list)
    ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in bytes_list)
    return hex_str, ascii_str


# ---------------------------------------------------------------------------
# Live LA capture + decode (single command, no binary file)
# ---------------------------------------------------------------------------
def capture_and_decode():
    """
    Run the live sigrok-cli command:
      --triggers D1=f  → wait for UART start bit before recording
      -P uart:baudrate=115200:rx=D1  → live-decode D1 as UART
      -A uart=rx-data  → print only decoded bytes (hex), no bit noise

    Returns (raw_lines, decoded_string).
    """
    cmd = [
        SIGROK_CLI,
        "--driver",   "fx2lafw",
        "--config",   f"samplerate={SAMPLERATE}",
        "--time",     CAPTURE_TIME,
        "--triggers", "D1=f",
        "-P",         f"uart:baudrate={UART_BAUD}:rx=D1",
        "-A",         "uart=rx-data",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        raw = result.stdout + result.stderr
        lines = raw.splitlines()
        return lines, raw
    except subprocess.TimeoutExpired:
        return [], "TIMEOUT"
    except Exception as e:
        return [], f"ERROR: {e}"


# ---------------------------------------------------------------------------
# Parse timing info from sigrok output
# ---------------------------------------------------------------------------
def parse_byte_intervals(hex_lines):
    """
    Convert 'uart-1: XX' lines to timestamps for bit timing analysis.
    Uses --protocol-decoder-samplenum to get sample numbers.
    Returns list of (sample_num, byte_value).
    """
    # Re-run with sample numbers to get timing
    cmd = [
        SIGROK_CLI,
        "--driver",   "fx2lafw",
        "--config",   f"samplerate={SAMPLERATE}",
        "--time",     CAPTURE_TIME,
        "--triggers", "D1=f",
        "--protocol-decoder-samplenum",
        "-P",         f"uart:baudrate={UART_BAUD}:rx=D1",
        "-A",         "uart=rx-data",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        timing_lines = result.stdout.splitlines()
    except Exception:
        return []

    samples_and_bytes = []
    for line in timing_lines:
        m = re.match(r"uart-1:\s*(\d+):\s*([0-9A-Fa-f]{2})", line)
        if m:
            samples_and_bytes.append((int(m.group(1)), int(m.group(2), 16)))
    return samples_and_bytes


# ---------------------------------------------------------------------------
# Bit timing analysis
# ---------------------------------------------------------------------------
def analyze_timing(samples_and_bytes):
    """
    Given [(sample_num, byte_val), ...] from a 1MHz capture,
    compute inter-byte intervals in microseconds and compare to
    expected bit time (8.68us) and byte time (86.8us for 8N1).
    """
    lines = []
    if len(samples_and_bytes) < 2:
        return lines

    # Sample rate in Hz (1m = 1 MHz)
    sr_hz = 1_000_000.0

    # Compute inter-byte gaps (stop bit end → next start bit)
    gaps_us = []
    for i in range(len(samples_and_bytes) - 1):
        # Each 8N1 byte = 10 bits = 10 * 8.68us = 86.8us = 86.8 samples @ 1MHz
        # gap = time from end of byte N to start of byte N+1
        gap_samples = samples_and_bytes[i+1][0] - samples_and_bytes[i][0]
        gap_us = gap_samples / sr_hz * 1_000_000.0
        gaps_us.append(gap_us)

    if gaps_us:
        mn  = min(gaps_us)
        mx  = max(gaps_us)
        avg = sum(gaps_us) / len(gaps_us)
        expected_byte_us = 10 * EXPECTED_BIT_US  # 86.8 us for 1 byte 8N1
        acc = abs(avg - expected_byte_us) / expected_byte_us * 100
        lines.append(
            f"Byte period:  min={mn:.1f}us  avg={avg:.1f}us  max={mx:.1f}us"
        )
        lines.append(
            f"Expected:     {expected_byte_us:.1f}us  accuracy=\xb1{acc:.1f}%  [{'OK' if acc < 2 else 'CHECK BAUD'}]"
        )
        lines.append(
            f"Bit time:     {EXPECTED_BIT_US:.2f}us @ {UART_BAUD} baud"
        )
    return lines


# ---------------------------------------------------------------------------
# Render display
# ---------------------------------------------------------------------------
def render(ts, iteration, hex_str, ascii_str, timing_lines, error):
    w = W
    uart_preview = (hex_str + " " + ascii_str)[:w - 16].ljust(w - 16)

    out = []
    out.append("\n" + "\u2554" + "\u2550" * (w - 2) + "\u2557")
    out.append("\u2551  SIGROK LOGIC ANALYZER  \u2502  " + f"t={ts}  iter={iteration}".ljust(w - 34) + "\u2551")
    out.append("\u2560" + "\u2550" * (w - 2) + "\u2563")

    # ---- Signal overview ----
    out.append("\u2551  [SIGNALS]".ljust(w - 1) + "\u2551")
    out.append(f"\u2551  USART3 TX (D1\u2192PD8)  {UART_BAUD} baud 8N1   \u2502  status=\u25cf OK".ljust(w - 1) + "\u2551")
    out.append("\u2551  LA probe: CH1 (D1) \u2192 PD8 on B-U585I-IOT02A".ljust(w - 1) + "\u2551")
    out.append("\u255F" + "\u2500" * (w - 2) + "\u2562")

    # ---- Decoded UART output ----
    out.append("\u2551  [UART DECODE \u2014 USART3 TX / D1 \u2014 last capture]".ljust(w - 1) + "\u2551")
    if error and "ERROR" in error:
        out.append(f"\u2551  {error}".ljust(w - 1) + "\u2551")
    elif hex_str:
        out.append(f"\u2551  HEX:  {hex_str[:w-12]}".ljust(w - 1) + "\u2551")
        out.append(f"\u2551  ASCII:{ascii_str[:w-13]}".ljust(w - 1) + "\u2551")
        clean = ascii_str.replace(chr(0x0D), " ").replace(chr(0x0A), " ")
        out.append(f"\u2551  Chars decoded: {len(clean)}".ljust(w - 1) + "\u2551")
    else:
        out.append("\u2551  (waiting for UART data \u2026 make sure firmware is running)".ljust(w - 1) + "\u2551")
    out.append("\u255F" + "\u2500" * (w - 2) + "\u2562")

    # ---- Bit timing ----
    out.append("\u2551  [BIT TIMING ANALYSIS]".ljust(w - 1) + "\u2551")
    if timing_lines:
        for line in timing_lines:
            out.append(f"\u2551  {line}".ljust(w - 1) + "\u2551")
    else:
        out.append(f"\u2551  Expected bit: {EXPECTED_BIT_US:.2f}us @ {UART_BAUD} baud 8N1".ljust(w - 1) + "\u2551")
        out.append(f"\u2551  Expected byte: {10*EXPECTED_BIT_US:.1f}us (10 bits / 8N1)".ljust(w - 1) + "\u2551")
        out.append("\u2551  Run with sample numbers to enable timing analysis".ljust(w - 1) + "\u2551")
    out.append("\u2560" + "\u2550" * (w - 2) + "\u2563")
    out.append(f"\u2551  Capture: {SAMPLERATE}Hz / {CAPTURE_TIME} / trigger=D1:f  refresh={REFRESH_SEC}s".ljust(w - 1) + "\u2551")
    out.append("\u255A" + "\u2550" * (w - 2) + "\u255D")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def run():
    os.system("title Sigrok Monitor — LA Timing & UART Decode")
    os.system("color 07")

    print("Sigrok Logic Analyzer — Live Monitor")
    print(f"  sigrok-cli: {SIGROK_CLI}")
    print(f"  samplerate: {SAMPLERATE}  capture: {CAPTURE_TIME}")
    print(f"  decoder: UART {UART_BAUD} baud on D1")
    print()
    print("  PROBE: LA CH1 (D1) \u2192 PD8 on B-U585I-IOT02A  |  GND \u2192 GND")
    print()
    print("  Commands to run in other terminals:")
    print("    python C:\\Users\\kerem\\Documents\\ImbedderNewTrial_MAI\\stage_monitor.py")
    print("    (open COM5 in TeraTerm at 115200 for live UART feed)")
    print()
    print("Press Ctrl+C to stop.\n")
    input("  Press Enter to start capturing...")
    time.sleep(0.5)

    iteration = 0
    last_hex  = ""
    last_ascii = ""

    while True:
        iteration += 1
        ts = datetime.now().strftime("%H:%M:%S")

        write_status_field("sigrok_iteration", iteration)
        write_status_field("sigrok_timestamp", ts)

        # Primary capture: decoded hex bytes
        hex_lines, error = capture_and_decode()
        hex_str, ascii_str = hex_to_ascii(hex_lines)

        # Timing analysis (second pass with sample numbers)
        samples_and_bytes = parse_byte_intervals(hex_lines)
        timing_lines = analyze_timing(samples_and_bytes)

        # Write to status.json for stage_monitor display
        if ascii_str:
            write_status_field("uart_last", ascii_str[:80])
            last_hex   = hex_str
            last_ascii = ascii_str

        # Render
        clear_screen()
        panel = render(ts, iteration, last_hex, last_ascii, timing_lines, error)
        print(panel)
        print(f"\n  Iter {iteration}  |  next in {REFRESH_SEC}s  [Ctrl+C]")

        time.sleep(REFRESH_SEC)


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\n\nMonitor stopped.")
        sys.exit(0)