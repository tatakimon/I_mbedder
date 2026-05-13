"""
stage_monitor.py — Window C of the HIL pipeline
Workflow stage tracker with progress bar and stage history.
Reads from status.json, written by the agent at each stage transition.

Run in its own terminal:
    python C:\\Users\\kerem\\Documents\\ImbedderNewTrial_MAI\\stage_monitor.py

Agent writes to status.json at each stage transition:
    {
      "stage":     "BUILD",
      "progress":  60,
      "detail":    "arm-none-eabi-gcc compiling main.c...",
    }
"""

import os
import sys
import json
import time
from datetime import datetime

STATUS_FILE     = "C:/Users/kerem/Documents/ImbedderNewTrial_MAI/status.json"
REFRESH_SECONDS = 1.0

STAGES = [
    "IDLE",
    "TEMPLATE_SELECT",
    "CLEAN_SLATE",
    "CODE_INJECT",
    "BUILD",
    "FLASH",
    "UART_VERIFY",
    "SAVED_BASE_TREE",
    "DONE",
]

STAGE_LABELS = {
    "IDLE":            "Idle — awaiting task",
    "TEMPLATE_SELECT": "Selecting template",
    "CLEAN_SLATE":     "Applying Clean Slate",
    "CODE_INJECT":     "Injecting sensor code",
    "BUILD":           "Building firmware",
    "FLASH":           "Flashing to MCU",
    "UART_VERIFY":     "Verifying UART output",
    "SAVED_BASE_TREE": "Saving to base_tree",
    "DONE":            "Task complete",
}

W = 76


def clear_screen():
    os.system("cls")


def read_status():
    try:
        with open(STATUS_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def elapsed(start_str):
    if not start_str:
        return "00:00:00"
    try:
        start = datetime.fromisoformat(start_str)
        delta = datetime.now() - start
        s = int(delta.total_seconds())
        return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"
    except Exception:
        return "00:00:00"


def render(stage, progress, detail, start_str, sigrok_iter):
    tick   = elapsed(start_str)
    filled = int(W * progress / 100)
    bar    = "█" * filled + "░" * (W - filled)

    idx = STAGES.index(stage) if stage in STAGES else 0

    lines = []
    lines.append("\n" + "\u2554" + "\u2550" * (W - 2) + "\u2557")
    lines.append("\u2551  STM32 Hybrid HIL \u2014 Workflow Stage Monitor".ljust(W - 1) + "\u2551")
    lines.append("\u2560" + "\u2550" * (W - 2) + "\u2563")
    lines.append(f"\u2551  [{bar}]  {progress}%".ljust(W - 1) + "\u2551")
    lines.append(f"\u2551  Stage:  {STAGE_LABELS.get(stage, stage).ljust(W - 12)}".ljust(W - 1) + "\u2551")
    lines.append(f"\u2551  Detail: {detail.ljust(W - 12)}".ljust(W - 1) + "\u2551")
    lines.append(f"\u2551  Tick:   {tick.ljust(W - 12)}".ljust(W - 1) + "\u2551")
    lines.append("\u2560" + "\u2550" * (W - 2) + "\u2563")

    # Stage pipeline
    lines.append("\u2551  Pipeline:".ljust(W - 1) + "\u2551")
    for i in range(0, len(STAGES), 2):
        left  = STAGES[i]
        right = STAGES[i + 1] if i + 1 < len(STAGES) else ""
        l_done = STAGES.index(left)  <= idx
        r_done = bool(right) and STAGES.index(right) <= idx
        l_icon = "\u25cf " if l_done else "\u25cb "
        r_icon = "\u25cf " if r_done else "\u25cb "
        line = f"\u2551    {l_icon}{left:<22} {r_icon}{right}".ljust(W - 1)
        if not right:
            line = line.rstrip()
        lines.append(line)

    lines.append("\u2560" + "\u2550" * (W - 2) + "\u2563")

    # Sigrok iteration
    if sigrok_iter and sigrok_iter > 0:
        ts = datetime.now().strftime("%H:%M:%S")
        lines.append(f"\u2551  LA captures: {sigrok_iter}  @ {ts}".ljust(W - 1) + "\u2551")
    else:
        lines.append("\u2551  LA captures: \u2014".ljust(W - 1) + "\u2551")

    # Last UART line
    try:
        data = read_status()
        uart = data.get("uart_last", "")
    except Exception:
        uart = ""

    if uart:
        display = uart[:W - 14].ljust(W - 14)
        lines.append("\u2551  \u250c\u2500\u2500\u2500 Last UART \u2500\u2500\u2500\u2510".ljust(W - 1) + "\u2551")
        lines.append(f"\u2551  {display}".ljust(W - 1) + "\u2551")
    else:
        lines.append("\u2551  Last UART: \u2014".ljust(W - 1) + "\u2551")

    lines.append("\u255A" + "\u2550" * (W - 2) + "\u255D")
    return "\n".join(lines)


def run_monitor():
    os.system("title Stage Monitor")
    os.system("color 07")

    print("Stage Monitor running...")
    print(f"  Reading: {STATUS_FILE}")
    print("  Press Ctrl+C to stop.\n")
    time.sleep(1.5)

    prev_stage = None

    while True:
        data = read_status()

        stage      = data.get("stage", "IDLE")
        progress   = data.get("progress", 0)
        detail     = data.get("detail", "\u2014")
        sigrok_iter = data.get("sigrok_iteration", 0)

        # Detect stage transition — reset elapsed timer
        if stage != prev_stage:
            prev_stage  = stage
            start_str   = datetime.now().isoformat()
            data["stage_start"] = start_str
            try:
                with open(STATUS_FILE, "w") as f:
                    json.dump(data, f, indent=2)
            except Exception:
                pass
        else:
            start_str = data.get("stage_start")

        clear_screen()
        panel = render(stage, progress, detail, start_str, sigrok_iter)
        print(panel)
        print(f"\n  Refreshing every {REFRESH_SECONDS}s  [Ctrl+C to stop]")
        time.sleep(REFRESH_SECONDS)


if __name__ == "__main__":
    try:
        run_monitor()
    except KeyboardInterrupt:
        print("\n\nMonitor stopped.")
        sys.exit(0)