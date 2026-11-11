---
name: kb-logs
description: Captures and prints RMKurchin split-keyboard firmware logs streamed over USB serial (CDC-ACM, defmt). Use when asked to view, read, inspect, or debug keyboard logs, firmware logs, or live defmt/BLE/host/GATT activity on the rmk-urchin keyboard.
compatibility: macOS, Python 3 (no third-party deps); the keyboard central half must be connected via USB.
---

# kb-logs — view RMKurchin keyboard logs

Runs `read_logs.py` to stream the firmware's defmt log output from the keyboard's
USB-serial (CDC-ACM) interface. No dependencies (termios via `ctypes`).

## Run

From the repo root, the script lives in `scripts/`:

```shell
./scripts/read_logs.py                 # 115200 baud, 8s
./scripts/read_logs.py 115200 30       # 30s
./scripts/read_logs.py 115200 0 --follow   # stream until Ctrl-C (auto-reconnects)
python3 scripts/read_logs.py 9600      # try 9600 if 115200 output is garbled
```

`skills/kb-logs/scripts/read_logs.py` is a symlink to `scripts/read_logs.py`
(single source of truth), so both paths behave identically.

## How it works

- A short-lived child process owns the serial port (where a `ctypes`/libc shutdown
  segfault can occur); the parent reads the pipe and prints text, so child crashes
  are invisible and re-spawning keeps `--follow` streaming.
- It auto-detects `/dev/cu.usbmodem*` / `/dev/cu.usbserial*`.

## Reading the output

- Logs are **event-driven** (BLE connect, GATT, key presses). Quiet moments produce
  little or nothing — that is normal, not a failure. Re-run or use `--follow`.
- Logs come from whichever half is plugged into USB (the **central** half is the USB host).
- Baud `115200` is the default; switch to `9600` if the output is garbled.
