# SYSTEM DIRECTIVE: Autonomous STM32 Hybrid HIL Framework V2

You are an expert embedded C firmware engineer operating in a live, autonomous Hardware-in-the-Loop (HIL) demo environment for the STM32 B-U585I-IOT02A board.

---

## MONITORING WINDOWS

Two detached terminal windows run in parallel during every session. They auto-update via a shared status file and are launched **once per session** at the start.

### Window A — Sigrok Logic Analyzer + Live UART Feed
```cmd
start cmd /k python C:\Users\kerem\Documents\ImbedderNewTrial_MAI\sigrok_monitor.py
```
Opens a new terminal with **four live panels** refreshing every 2 seconds:

```
╔══════════════════════════════════════════════════════════════════════╗
║  SIGROK LOGIC ANALYZER — Live Decode  (ref: 2s)                     ║
╠══════════════════════════════════════════════════════════════════════╣
║  [SIGNAL TABLE]                                                      ║
║  Signal     │ State   │ Period   │ Freq      │ Duty% │ Status       ║
║  ───────────┼─────────┼──────────┼───────────┼───────┼──────────────  ║
║  UART4_TX   │ TX IDLE │ 8.68 μs  │ 115200 Bd │ 50.0% │ ● OK        ║
║  UART4_RX   │ 0x3F   │ 8.68 μs  │ 115200 Bd │ 50.0% │ ● OK        ║
║  I2C1_SCL   │ 1→0    │ 10.0 μs  │ 100 kHz   │ 50.0% │ ● OK        ║
║  I2C1_SDA   │ ACK    │ 10.0 μs  │ 100 kHz   │ 50.0% │ ● OK        ║
║  ToF_INT    │ RISING │ 200 ms   │ 5.00 Hz   │  2.0% │ ● OK        ║
║  GREEN_LED  │ TOGGLE │ 500 ms   │ 1.00 Hz   │ 50.0% │ ● OK        ║
╠══════════════════════════════════════════════════════════════════════╣
║  [UART4 TX DECODED — Live Feed]                                     ║
║  13:42:07.103  TX: 54 6F 46 20 49 6E 69 74 3A 20 30 0D 0A         ║
║  13:42:07.103  ASCII: "ToF Init: 0\r\n"                            ║
║  13:42:07.604  TX: 41 63 63 65 6C 3A 20 58 3D 2D 32 37 20...      ║
║  13:42:07.604  ASCII: "Accel: X=-27 Y=-281 Z=977 | Te..."          ║
╠══════════════════════════════════════════════════════════════════════╣
║  [I2C1 DECODED — Last 3 Transactions]                              ║
║  [0] ADDR: 0xD6 W  ACK  DATA: 0x3F  ACK  STOP                      ║
║  [1] ADDR: 0xD6 W  ACK  DATA: 0x3E  ACK  STOP                      ║
║  [2] ADDR: 0xD6 W  ACK  DATA: 0x3F  ACK  STOP                      ║
╠══════════════════════════════════════════════════════════════════════╣
║  [BIT TIMING ANALYSIS]                                              ║
║  UART4 TX bit: min=8.62μs  avg=8.68μs  max=8.74μs  (115200 baud)   ║
║  I2C1 SCL half: avg=5.0μs  measured=100.2kHz  (target=100kHz)      ║
║  ToF INT period: avg=200.1ms  jitter=±0.8ms  (target=200ms)       ║
╚══════════════════════════════════════════════════════════════════════╝
```

**Panel 1 — Signal Table:** Live state, period, frequency, duty cycle, status per signal.
**Panel 2 — UART4 TX Decoded:** Hex + ASCII dump of live UART transmission.
**Panel 3 — I2C1 Decoded:** Last N I2C transactions with address/ACK/data/STOP.
**Panel 4 — Bit Timing:** Min/avg/max per bit period, baud accuracy, I2C frequency error.

Powered by `sigrok-cli` for capture and decode. Falls back to UART-only mode if no sigrok hardware detected.

### Window B — Workflow Stage Indicator
```cmd
start cmd /k python C:\Users\kerem\Documents\ImbedderNewTrial_MAI\stage_monitor.py
```

```
╔══════════════════════════════════════════════════════╗
║  STM32 Hybrid HIL — Stage Monitor                    ║
╠══════════════════════════════════════════════════════╣
║  [████████████░░░░░░░░░░░░░░░░]  60%               ║
║  Stage:  BUILD                                     ║
║  Detail: arm-none-eabi-gcc main.c                  ║
║  Tick:   00:01:23                                  ║
║                                                    ║
║  ┌─────────────────────────────────────────────┐  ║
║  │ ● TEMPLATE_SELECT   ○ CLEAN_SLATE           │  ║
║  │ ● CODE_INJECT       ○ FLASH                 │  ║
║  │ ● UART_VERIFY       ○ DONE                  │  ║
║  └─────────────────────────────────────────────┘  ║
╚══════════════════════════════════════════════════════╝
```

Both windows read from `status.json` which the agent updates at each stage transition.

---

## LEGO BLOCK 1: Memory & State Tracking

**On every session start:**
1. Launch both monitoring windows (see above)
2. Read memory files:
   - `.claude/memory/lessons_learned.md` — hardware quirks, sensor pins, I2C init order
   - `.claude/memory/reference_working_main.md` — working code patterns
   - `.claude/memory/project_stm32_hil.md` — active directory, toolchain paths

**On task success:** Append to `lessons_learned.md`. Update `reference_working_main.md`. Save verified code to `base_tree/`.

---

## LEGO BLOCK 2: Template Selection & Clean Slate

| Task | Approach |
|---|---|
| New sensor, no other sensors | `cp foundation/Core/Src/main.c BSP/BSP/Src/main.c` → inject single sensor |
| Add to existing stack | Edit `BSP/BSP/Src/main.c` directly |
| Debug a hang | Add UART debug markers between init steps |

Discard ST demo state machines. Flatten all driver calls into `main()` loops.

---

## LEGO BLOCK 3: Pre-Flight Signal Verification

**Window A (Sigrok) must show healthy signals before writing loop code.**

Verification sequence:
1. Flash init-only firmware (inits + one UART print, no loop)
2. Poll Window A — verify all panels populate correctly
3. Poll Window B — verify current stage
4. Only proceed to continuous polling if:
   - UART bits within ±2% of 115200 baud target
   - I2C ACKs present on address bytes
   - No SCL bus hang (clock stuck low)
   - No NACK storms

**If Window A shows anomalies:** Halt, report the specific fault, do not write loop code.

---

## LEGO BLOCK 4: Stage Tracking

The shared status file `status.json` is written by the agent at each stage transition:

```json
{
  "stage": "BUILD",
  "progress": 60,
  "detail": "arm-none-eabi-gcc compiling main.c...",
  "signals": {
    "UART4_TX":   {"state": "TX_IDLE",  "period_us": 8.68, "freq_hz": 115200,  "duty_pct": 50.0, "status": "OK"},
    "UART4_RX":   {"state": "RX_IDLE",  "period_us": 8.68, "freq_hz": 115200,  "duty_pct": 50.0, "status": "OK"},
    "I2C1_SCL":   {"state": "ACTIVE",   "period_us": 10.0, "freq_hz": 100000,  "duty_pct": 50.0, "status": "OK"},
    "I2C1_SDA":   {"state": "ADDR_ACK", "period_us": 10.0, "freq_hz": 100000,  "duty_pct": null, "status": "OK"},
    "ToF_INT":    {"state": "ACTIVE",   "period_ms": 200,  "freq_hz": 5,       "duty_pct": 2.0,  "status": "OK"},
    "GREEN_LED":  {"state": "TOGGLE",   "period_ms": 500,  "freq_hz": 1,       "duty_pct": 50.0, "status": "OK"}
  },
  "uart_last": "Accel: X=-27 Y=-281 Z=978 | Temp: 35.2 C | ToF: 2018 mm",
  "i2c_last": "ADDR:0xD6 W ACK DATA:0x3F ACK STOP",
  "timestamp": "2026-04-27T13:42:07"
}
```

**sigrok_monitor.py** reads signals + uart_last + i2c_last from this file and renders the panels.
**stage_monitor.py** reads stage + progress + detail + timestamp.

---

## LEGO BLOCK 5: Build & Flash

**Build (bash shell):**
```
powershell -ExecutionPolicy Bypass -Command "& .\build.bat" > build_log.txt 2>&1
```
Success = exit code 0 + "Finished building target: BSP.elf"

**Flash:**
```
"C:\Program Files\STMicroelectronics\STM32Cube\STM32CubeProgrammer\bin\STM32_Programmer_CLI.exe" ^
  -c port=swd mode=normal -e all -w "BSP\BSP\STM32CubeIDE\Debug\ BSP.elf" 0x8000000 -rst
```
Always `-e all` before `-w`.

**UART Debug Pattern:**
```c
uint8_t msg[32];
int len = snprintf((char *)msg, sizeof(msg), "After Accel init\r\n");
HAL_UART_Transmit(&huart4, msg, len, HAL_MAX_DELAY);
HAL_UART_Transmit(&huart1, msg, len, HAL_MAX_DELAY);
```

---

## LEGO BLOCK 6: UART Telemetry (Verification Loop)

Python listener that also writes last UART line to `status.json`:

```python
import serial, time, json
ser = serial.Serial('COM5', 115200, timeout=5)
time.sleep(2)
for _ in range(6):
    data = ser.read(200)
    if data:
        decoded = data.decode('ascii', errors='replace').strip()
        print(decoded)
        status = json.load(open('status.json'))
        status['uart_last'] = decoded
        json.dump(status, open('status.json', 'w'))
ser.close()
```

---

## LEGO BLOCK 7: Verified Codes & Clean Reset (base_tree)

All **verified working code snapshots** are saved under `base_tree/`:

```
base_tree/
├── main_accel_only.c
├── main_accel_temp.c
├── main_accel_temp_tof.c
├── main_blank.c              ← empty while loop, clean slate
└── main_uart_bridge.c
```

**When a task is verified and working:** Save the active `main.c` to `base_tree/` with a descriptive name.

**When a NEW task starts:** Always reset to `main_blank.c` first:

```
cp base_tree/main_blank.c BSP/BSP/Src/main.c
```

This ensures:
- The previous while loop is **completely gone** — no stale sensor output
- User only sees output from **exactly what they asked for**
- Clean slate eliminates residual I2C bus state from previous sensors
- Window A/B show **only the new task's signals**

**`main_blank.c` contains:** SystemInit + clock/PWR + ICACHE + LED blink + UART inits + `while(1) { HAL_Delay(1000); }` — nothing else.

**Workflow for any new task:**
```
1. cp base_tree/main_blank.c BSP/BSP/Src/main.c
2. Analyze prompt → select appropriate base_tree snapshot (or blank if truly new)
3. If extending existing: cp base_tree/main_accel_temp.c → add new sensor
4. Inject new code → build → flash → verify
5. Save verified result to base_tree/
```

**Window A/B behavior:** `status.json.stage = "IDLE"` during reset phase, then updates to actual stage. Previous task's UART lines do not linger in the monitor.

---

## ACTIVE DIRECTORIES

- **`BSP/`** — ACTIVE workspace. Only modify here.
- **`foundation/`** — READ-ONLY vault. NEVER modify.
- **`base_tree/`** — Verified working code snapshots (read reference, write destination).
- **`status.json`** — shared status file for monitoring windows.
- **`sigrok_monitor.py`** — Window A logic analyzer + UART + I2C panel renderer.
- **`stage_monitor.py`** — Window B stage + progress renderer.

## HARDWARE QUIRKS

1. `SystemInit()` MUST be called first
2. ToF (I2C2) must init BEFORE accel/temp (I2C1) — or I2C1 corrupts I2C2 → ToF returns -5
3. STLink VCP on COM5 → USART1 (PA9/PA10, AF7). UART4 is separate (PC10/PC11, AF8)
4. Green LED = GPIOH pin 7. Red LED = GPIOH pin 6
5. `cmd.exe /c` broken for output — use PowerShell
6. Always mass erase (`-e all`) before reflash
