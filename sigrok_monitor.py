"""
sigrok_monitor.py — Window A
Bit timing + signal analysis via LA decode.
No box-drawing — clean terminal output showing timing data per byte.

Run in its own terminal:
    python C:\\Users\\kerem\\Documents\\ImbedderNewTrial_MAI\\sigrok_monitor.py
"""

import subprocess
import json
import os
import time
import re
from datetime import datetime

SIGROK_CLI   = "C:/Program Files/sigrok/sigrok-cli/sigrok-cli.exe"
STATUS_FILE  = "C:/Users/kerem/Documents/ImbedderNewTrial_MAI/status.json"
SAMPLERATE   = "1m"
CAPTURE_TIME = "500ms"
UART_BAUD    = 115200
REFRESH_SEC  = 3.0
SR_HZ        = 1_000_000.0          # 1 MHz
BIT_US       = 1_000_000.0 / UART_BAUD   # 8.68 us
BYTE_US      = 10 * BIT_US               # 86.8 us


def clear():
    os.system("cls")


def write_status(key, value):
    try:
        d = json.load(open(STATUS_FILE)) if os.path.exists(STATUS_FILE) else {}
        d[key] = value
        json.dump(d, open(STATUS_FILE, "w"), indent=2)
    except Exception:
        pass


def find_la_conn():
    """Run --scan and extract current fx2lafw conn value."""
    try:
        result = subprocess.run(
            [SIGROK_CLI, "--scan"], capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            if "fx2lafw" in line and "Saleae Logic" in line:
                # e.g. "fx2lafw:conn=2.14 - Saleae Logic ..."
                m = re.search(r"fx2lafw:conn=(\S+)", line)
                if m:
                    return m.group(1)
    except Exception:
        pass
    return None


def capture_with_timing():
    """Single sigrok-cli command: scan for LA, capture + decode + sample numbers.
    Returns list of (sample_num, byte_val).
    """
    conn = find_la_conn()
    if conn is None:
        return []

    cmd = [
        SIGROK_CLI, "--driver", f"fx2lafw:conn={conn}",
        "--config", f"samplerate={SAMPLERATE}",
        "--time",   CAPTURE_TIME,
        "--triggers", "D1=f",
        "--protocol-decoder-samplenum",
        "-P", f"uart:baudrate={UART_BAUD}:rx=D1",
        "-A", "uart=rx-data",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    except Exception:
        return []
    pairs = []
    for line in result.stdout.splitlines():
        # Format: "209317-209387 uart-1: 54"  →  start sample, byte value
        m = re.match(r"(\d+)-\d+ uart-1:\s*([0-9A-Fa-f]{2})", line)
        if m:
            pairs.append((int(m.group(1)), int(m.group(2), 16)))
    return pairs


def render(ts, iteration, pairs, error):
    lines = []

    # --- Header ---
    lines.append(f"[{ts}] sigrok_monitor  iter={iteration}  rate={SR_HZ/1e6:.0f}MHz  capture={CAPTURE_TIME}  trigger=D1:f")
    lines.append("")

    if error:
        lines.append(f"ERROR: {error}")
        return "\n".join(lines)

    if len(pairs) < 1:
        lines.append("(no UART data - is firmware running on the board?)")
        lines.append(f"LA channel: D1 (CH1 probe) -> PD8 on B-U585I-IOT02A")
        lines.append(f"Baud: {UART_BAUD} 8N1  |  refresh every {REFRESH_SEC}s")
        return "\n".join(lines)

    # --- Decoded text ---
    hex_str = " ".join(f"{v:02X}" for _, v in pairs)
    ascii_str = "".join(chr(v) if 32 <= v < 127 else "." for _, v in pairs)
    ascii_str = ascii_str.replace("\r", " ").replace("\n", " ")
    lines.append(f"TEXT : {ascii_str}")
    lines.append(f"HEX  : {hex_str}")
    lines.append(f"BYTES: {len(pairs)} chars decoded")
    lines.append("")

    # --- Per-byte timing table ---
    lines.append("PER-BYTE TIMING (1 MHz = 1 us/sample)")
    lines.append(f"{'#':>3}  {'B':>3}  {'ASCII':>5}  {'us@1MHz':>9}  {'us':>8}  gap_us   accuracy")
    lines.append("-" * 58)

    gaps = []
    for i, (sample, val) in enumerate(pairs):
        ascii_c = chr(val) if 32 <= val < 127 else "."
        abs_us = sample  # 1 sample = 1 us @ 1MHz

        if i == 0:
            gap_disp = "  --  "
            acc_disp = "  --  "
        else:
            gap_us = sample - pairs[i-1][0]
            gaps.append(gap_us)
            acc_pct = abs(gap_us - BYTE_US) / BYTE_US * 100
            gap_disp = f"{gap_us:>6.1f}"
            acc_disp = f"{acc_pct:>5.1f}%"

        lines.append(
            f"{i+1:>3}  0x{val:02X}  {ascii_c!r:>5}  "
            f"{sample:>9}  {abs_us:>7.0f}us  {gap_disp}   {acc_disp}"
        )

    # --- Summary ---
    if gaps:
        mn  = min(gaps)
        mx  = max(gaps)
        avg = sum(gaps) / len(gaps)
        acc = abs(avg - BYTE_US) / BYTE_US * 100
        lines.append("")
        lines.append(f"EXPECTED BYTE PERIOD : {BYTE_US:.1f} us (10 bits @ {UART_BAUD} baud)")
        lines.append(f"MEASURED BYTE PERIOD: min={mn:.1f}us  avg={avg:.1f}us  max={mx:.1f}us")
        lines.append(f"ACCURACY             : {'OK' if acc < 2 else 'CHECK BAUD'}  (avg error = {acc:.1f}%)")
        lines.append(f"BIT TIME             : {BIT_US:.2f} us")
    else:
        lines.append("")
        lines.append(f"(need 2+ bytes for gap/timing analysis)")

    return "\n".join(lines)


def run():
    os.system("title Sigrok Monitor")
    print("sigrok_monitor.py — Bit timing via LA decode")
    print(f"  LA: D1 (CH1) -> PD8  |  {UART_BAUD} baud 8N1")
    print(f"  refresh every {REFRESH_SEC}s")
    print()
    print("  TERA TERM ALTERNATIVE for live text feed:")
    print("    python uart_feed.py")
    print()
    input("  Press Enter to start capturing...")
    clear()

    iteration = 0
    last_text = ""

    while True:
        iteration += 1
        ts = datetime.now().strftime("%H:%M:%S")

        write_status("sigrok_iteration", iteration)
        write_status("sigrok_timestamp", ts)

        pairs = capture_with_timing()

        # Build display text from decoded bytes
        if pairs:
            ascii_str = "".join(chr(v) if 32 <= v < 127 else "." for _, v in pairs)
            ascii_str = ascii_str.replace("\r", " ").replace("\n", " ")
            write_status("uart_last", ascii_str[:80])
            last_text = ascii_str

        clear()
        panel = render(ts, iteration, pairs, None)
        print(panel)
        print(f"\n  iter={iteration}  next in {REFRESH_SEC}s  [Ctrl+C to stop]")

        time.sleep(REFRESH_SEC)


if __name__ == "__main__":
    import sys
    try:
        run()
    except KeyboardInterrupt:
        print("\nstopped.")
        sys.exit(0)