# I_mbedder — STM32 Hybrid HIL Framework

**Autonomous firmware development environment for the STM32 B-U585I-IOT02A board.** Uses a "Hybrid" architecture that combines a pre-built BSP workspace with a clean reference template to prevent build failures and enable reliable hardware-in-the-loop iteration.

---

## What It Does

Runs three sensors simultaneously and prints real-time data over UART (115200 baud, COM5):

```
ToF Init: 0 | Accel OK | Temp OK
Accel: X=-28 Y=-281 Z=977 | Temp: 35.1 C | ToF: 2022 mm
Accel: X=-27 Y=-280 Z=978 | Temp: 35.2 C | ToF: 2018 mm
...
```

- **Accelerometer** — ISM330DHCX (I2C, mg units)
- **Temperature** — HTS221 (I2C, Celsius)
- **Time-of-Flight** — VL53L5CX 4x4 grid (I2C, mm)

---

## Quick Start

### 1. Build

```cmd
build.bat
```

Or from PowerShell:
```powershell
powershell -ExecutionPolicy Bypass -Command "& .\build.bat" > build_log.txt 2>&1
```

Output: `BSP/BSP/STM32CubeIDE/Debug/BSP.elf`

### 2. Flash

```cmd
"C:\Program Files\STMicroelectronics\STM32Cube\STM32CubeProgrammer\bin\STM32_Programmer_CLI.exe" ^
  -c port=swd mode=normal -e all -w "BSP\BSP\STM32CubeIDE\Debug\BSP.elf" 0x8000000 -rst
```

### 3. Listen

```python
import serial
ser = serial.Serial('COM5', 115200, timeout=5)
for _ in range(10):
    print(ser.readline().decode(), end='')
ser.close()
```

---

## Architecture

```
ImbedderNewTrial_MAI/
├── BSP/                    # Active build workspace (BSP Makefile + drivers)
│   └── BSP/
│       ├── Src/main.c     # ← Edit this file only
│       ├── Drivers/        # BSP sensor drivers (do not modify)
│       └── STM32CubeIDE/Debug/  # Build output
├── foundation/            # READ-ONLY pristine template vault
└── build.bat              # Build script
```

### Why This Architecture?

The STMicroelectronics demo `main.c` is "spaghetti code" — it uses semihosting and calls demo menu logic before peripherals are initialized, which causes hangs. This project provides a clean baseline `main.c` (in `foundation/`) and a BSP workspace that already knows how to link all sensor drivers. You copy the clean template into the BSP workspace, then inject flattened sensor code on top of it.

### Workflow

1. `cp foundation/Core/Src/main.c BSP/BSP/Src/main.c` — reset to clean slate
2. Read `BSP/BSP/Src/*.c` demo files to extract raw sensor commands
3. Inject commands into `BSP/BSP/Src/main.c`
4. `build.bat` → flash → verify

**Rule:** Never modify any Makefile. Never modify anything in `foundation/`.

---

## Directory Reference

| Directory | Purpose |
|---|---|
| `BSP/BSP/Src/main.c` | Active firmware — code lives here |
| `BSP/BSP/Drivers/BSP/B-U585I-IOT02A/` | Sensor BSP headers |
| `BSP/BSP/Drivers/BSP/Components/` | Low-level component drivers |
| `BSP/BSP/STM32CubeIDE/Debug/` | Build artifacts (`BSP.elf`) |
| `foundation/Core/Src/main.c` | Clean template (read-only) |

---

## Sensor Reference

### Accelerometer — ISM330DHCX

```c
BSP_MOTION_SENSOR_Init(0, MOTION_ACCELERO);
BSP_MOTION_SENSOR_Enable(0, MOTION_ACCELERO);
BSP_MOTION_SENSOR_GetAxes(0, MOTION_ACCELERO, &axes);
// axes.xval, .yval, .zval  (int32_t, mg units)
```

### Temperature — HTS221

```c
BSP_ENV_SENSOR_Init(0, ENV_TEMPERATURE);
BSP_ENV_SENSOR_Enable(0, ENV_TEMPERATURE);
BSP_ENV_SENSOR_GetValue(0, ENV_TEMPERATURE, &temp); // float
```

### Time-of-Flight — VL53L5CX (4x4 grid)

```c
// Init FIRST — uses I2C2 (separate from accel/temp on I2C1)
BSP_RANGING_SENSOR_Init(VL53L5A1_DEV_CENTER);
RANGING_SENSOR_ProfileConfig_t prof = {
    .RangingProfile = RS_PROFILE_4x4_CONTINUOUS,
    .TimingBudget = 30, .Frequency = 5,
    .EnableAmbient = 0, .EnableSignal = 0
};
BSP_RANGING_SENSOR_ConfigProfile(VL53L5A1_DEV_CENTER, &prof);
BSP_RANGING_SENSOR_Start(VL53L5A1_DEV_CENTER, RS_MODE_BLOCKING_CONTINUOUS);

// In loop:
RANGING_SENSOR_Result_t dist;
BSP_RANGING_SENSOR_GetDistance(VL53L5A1_DEV_CENTER, &dist);
dist.ZoneResult[0].Distance[0]; // center zone, mm
```

### Humidity — HTS221

```c
BSP_ENV_SENSOR_Init(0, ENV_HUMIDITY);
BSP_ENV_SENSOR_Enable(0, ENV_HUMIDITY);
BSP_ENV_SENSOR_GetValue(0, ENV_HUMIDITY, &humidity); // float
```

### Pressure — LPS22HH

```c
BSP_ENV_SENSOR_Init(1, ENV_PRESSURE);
BSP_ENV_SENSOR_Enable(1, ENV_PRESSURE);
BSP_ENV_SENSOR_GetValue(1, ENV_PRESSURE, &pressure); // float
```

---

## Hardware Pins

| Signal | Pin | Alt Func |
|---|---|---|
| UART4 TX | PC10 | AF8 |
| UART4 RX | PC11 | AF8 |
| USART1 TX | PA9 | AF7 |
| USART1 RX | PA10 | AF7 |
| Green LED | PH7 | — |
| Red LED | PH6 | — |

ST-Link Virtual COM Port on COM5 → USART1 (PA9/PA10).

---

## Sensor Init Order

**CRITICAL:** The B-U585I-IOT02A has two I2C buses:
- **I2C1** → accelerometer, magnetometer, env sensors
- **I2C2** → VL53L5CX ToF sensor

If ToF is initialized after accel/temp, I2C1 init corrupts I2C2 state. **Correct order: ToF → Accel → Temp**, then read all in the loop.

---

## Toolchain

Uses GNU ARM Embedded Toolchain 13.3.rel1 via STM32CubeIDE 1.19.0. Build script (`build.bat`) sets the correct PATH automatically.

---

## Credits

Built on top of [STMicroelectronics BSP for B-U585I-IOT02A](https://www.st.com/en/evaluation-tools/b-u585i-iot02a.html).
