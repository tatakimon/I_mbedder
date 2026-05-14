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
SIGROK_CLI     = "C:/Program Files/sigrok/sigrok-cli/sigrok-cli.exe"
STATUS_FILE    = "C:/Users/kerem/Documents/ImbedderNewTrial_MAI/status.json"
LOG_FILE       = "C:/Users/kerem/Documents/ImbedderNewTrial_MAI/sigrok_log.txt"
SAMPLERATE     = "1m"
CAPTURE_TIME   = "500ms"
UART_BAUD      = 115200
REFRESH_SEC    = 3.0
SR_HZ          = 1_000_000.0
BIT_US         = 1_000_000.0 / UART_BAUD
BYTE_US        = 10 * BIT_US
IDLE_THRESH_US = 1000          # 1 ms — gaps larger than this are inter-frame idle


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
    lines.append(f"[{ts}] sigrok_monitor  iter={iteration}  rate={SR_HZ/1e6:.0f}MHz  capture={CAPTURE_TIME}  trigger=D1:f  idle_thresh={IDLE_THRESH_US}us")
    lines.append("")

    if error:
        lines.append(f"ERROR: {error}")
        return "\n".join(lines)

    if len(pairs) < 1:
        lines.append("(no UART data - is firmware running on the board?)")
        lines.append(f"LA channel: D1 (CH1 probe) -> PD8 on B-U585I-IOT02A")
        lines.append(f"Baud: {UART_BAUD} 8N1  |  refresh every {REFRESH_SEC}s")
        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # Compute gap_us for each byte (from previous byte's sample number)
    # -------------------------------------------------------------------------
    enriched = []
    for i, (sample, val) in enumerate(pairs):
        if i == 0:
            gap_us = 0
        else:
            gap_us = sample - pairs[i - 1][0]
        enriched.append((sample, val, gap_us))

    # -------------------------------------------------------------------------
    # Identify frames: split at gaps > IDLE_THRESH_US
    # Each frame = consecutive bytes within a single UART burst
    # -------------------------------------------------------------------------
    frames = []
    frame = []
    for sample, val, gap_us in enriched:
        if gap_us > IDLE_THRESH_US and frame:
            frames.append(frame)
            frame = []
        frame.append((sample, val, gap_us))
    if frame:
        frames.append(frame)

    # -------------------------------------------------------------------------
    # TEXT reconstruction: separate frames with " | ", strip 0xFF, strip control chars
    # -------------------------------------------------------------------------
    frame_texts = []
    for frame in frames:
        chars = []
        for _, val, gap_us in frame:
            if val == 0xFF:
                continue  # filter idle-line glitch
            if 32 <= val < 127:
                chars.append(chr(val))
            elif val in (0x0D, 0x0A):
                chars.append(".")
        frame_texts.append("".join(chars))
    text_str = " | ".join(frame_texts)

    hex_str = " ".join(f"{v:02X}" for _, v, _ in enriched)
    lines.append(f"TEXT : {text_str}")
    lines.append(f"HEX  : {hex_str}")
    lines.append(f"FRAMES: {len(frames)}  BYTES: {len(pairs)}")
    lines.append(f"IDLE_THRESH: {IDLE_THRESH_US} us  (gaps above this are inter-frame, excluded from accuracy)")
    lines.append("")

    # -------------------------------------------------------------------------
    # Per-byte timing table — shows all bytes so gaps > threshold are visible
    # accuracy column shows -- for inter-frame gaps
    # -------------------------------------------------------------------------
    lines.append("PER-BYTE TIMING (1 MHz = 1 us/sample)")
    lines.append(f"{'#':>3}  {'B':>4}  {'ASCII':>5}  {'sample':>9}  {'us':>7}  {'gap_us':>8}  accuracy")
    lines.append("-" * 62)

    for i, (sample, val, gap_us) in enumerate(enriched):
        ascii_c = chr(val) if 32 <= val < 127 else "."

        if gap_us == 0:
            gap_disp = "  --  "
            acc_disp = "  --  "
        elif gap_us > IDLE_THRESH_US:
            gap_disp = f"{gap_us:>6.0f}*"   # mark inter-frame gap
            acc_disp = "  --  "              # don't compute accuracy for idle
        else:
            acc_pct = abs(gap_us - BYTE_US) / BYTE_US * 100
            gap_disp = f"{gap_us:>6.1f}"
            acc_disp = f"{acc_pct:>5.1f}%"

        lines.append(
            f"{i+1:>3}  0x{val:02X}  {ascii_c!r:>5}  {sample:>9}  "
            f"{sample:>7.0f}us  {gap_disp}  {acc_disp}"
        )

    # -------------------------------------------------------------------------
    # Summary — accuracy based only on intra-frame gaps (below threshold)
    # -------------------------------------------------------------------------
    intra_gaps = [g for _, _, g in enriched if g > 0 and g <= IDLE_THRESH_US]
    if intra_gaps:
        mn  = min(intra_gaps)
        mx  = max(intra_gaps)
        avg = sum(intra_gaps) / len(intra_gaps)
        acc = abs(avg - BYTE_US) / BYTE_US * 100
        lines.append("")
        lines.append(f"INTRA-FRAME GAPS (gaps <= {IDLE_THRESH_US} us): {len(intra_gaps)}")
        lines.append(f"EXPECTED BYTE PERIOD : {BYTE_US:.1f} us (10 bits @ {UART_BAUD} baud)")
        lines.append(f"MEASURED BYTE PERIOD: min={mn:.1f}us  avg={avg:.1f}us  max={mx:.1f}us")
        lines.append(f"ACCURACY             : {'OK' if acc < 2 else 'CHECK BAUD'}  (avg error = {acc:.1f}%)")
        lines.append(f"BIT TIME             : {BIT_US:.2f} us")
    else:
        lines.append("")
        lines.append("(no intra-frame gaps — firmware may be sending single bytes)")

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

    while True:
        iteration += 1
        ts = datetime.now().strftime("%H:%M:%S")

        write_status("sigrok_iteration", iteration)
        write_status("sigrok_timestamp", ts)

        pairs = capture_with_timing()

        # Build display text from frames, strip 0xFF, separate with |
        if pairs:
            enriched = []
            for i, (sample, val) in enumerate(pairs):
                gap_us = 0 if i == 0 else sample - pairs[i - 1][0]
                enriched.append((sample, val, gap_us))

            frames = []
            frame = []
            for sample, val, gap_us in enriched:
                if gap_us > IDLE_THRESH_US and frame:
                    frames.append(frame)
                    frame = []
                frame.append((sample, val, gap_us))
            if frame:
                frames.append(frame)

            frame_texts = []
            for f in frames:
                chars = []
                for _, val, _ in f:
                    if val == 0xFF:
                        continue
                    if 32 <= val < 127:
                        chars.append(chr(val))
                    elif val in (0x0D, 0x0A):
                        chars.append(".")
                frame_texts.append("".join(chars))
            text_str = " | ".join(frame_texts)
            write_status("uart_last", text_str[:80])
        else:
            text_str = ""

        clear()
        panel = render(ts, iteration, pairs, None)
        # Log to file + print to console
        for line in panel.splitlines():
            print(line)
            append_log(LOG_FILE, line)
        footer = f"\n  iter={iteration}  next in {REFRESH_SEC}s  [Ctrl+C to stop]"
        print(footer)
        append_log(LOG_FILE, footer)

        time.sleep(REFRESH_SEC)


if __name__ == "__main__":
    import sys
    try:
        run()
    except KeyboardInterrupt:
        print("\nstopped.")
        sys.exit(0)