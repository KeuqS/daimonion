# MicroPython firmware

The template can generate a **MicroPython** project: firmware for a
microcontroller (ESP32, RP2/Pico, STM32, ...), deployed with
[mpremote](https://docs.micropython.org/en/latest/reference/mpremote.html).
Unlike a normal Python package, the code runs *on the device*, so the
CPython toolchain (uv/ruff/pytest/basedpyright) is used for the parts that
run on your computer:

- **`firmware/`** — the code that runs on the device. `boot.py` runs first,
  then MicroPython auto-runs `/main.py`. `board_config.py` holds the
  board-specific pins; `core/` holds device-independent logic.
- **`tests/`** — CPython `pytest` tests for `firmware/core`. `core` never
  imports `machine`, so it runs under normal CPython.
- **`typings/`** — MicroPython type stubs (`micropython-<port>-stubs`),
  installed *into a folder* rather than the venv so they don't shadow
  CPython's stdlib during host-side checking.

> [!NOTE]
> The type stubs come from the community
> [josverl/micropython-stubs](https://github.com/josverl/micropython-stubs)
> project — they are **not** published by the official MicroPython project.
> They are pinned (`~=`) to the same MicroPython release the frozen build
> targets (`micropython_version` in `copier.yml` → freeze.py's `DEFAULT_TAG`),
> so stubs and firmware stay in step. The firmware itself is the source of
> truth; treat the stubs as an editor aid.

## Choosing a port

| Port | Typical board | Notes |
|------|---------------|-------|
| **esp32** | ESP32 DevKitC | Most common; default |
| **esp8266** | NodeMCU | Legacy, low memory |
| **rp2** | Raspberry Pi Pico / Pico W | RP2040 / RP2350 |
| **stm32** | Pyboard | STM32 family |
| **samd** | Adafruit ItsyBitsy M0 | SAMD21 / SAMD51 |
| **unix** | your computer | Runs on the host — handy for tests |
| **windows** | your computer | Windows port |
| **mimxrt** | Teensy 4.x | NXP i.MX RT |

The `micropython-<port>-stubs` package describes the port's *generic* board.
Per-board differences (which GPIO the LED is on, etc.) are concentrated in
`firmware/board_config.py`, so moving to another board is a one-file edit.

## Setting up the dev environment

```sh
uv sync                              # ruff / pytest / basedpyright / mpremote / pyrefly|ty
uv run pip install -r requirements-dev.txt --target typings   # port stubs
```

The stubs are installed into `typings/` (git-ignored) so `basedpyright` can
type-check `firmware/` against MicroPython while `tests/` and
`firmware/core/` are checked against CPython. The secondary checker
(`type_checker`: pyrefly by default, or ty) runs over the CPython-side code
(`tests/` + `firmware/core/`); the firmware's hardware files (`main.py`,
`boot.py`, `board_config.py`) are checked only by the dedicated basedpyright
pass against the stubs.

## Running the tests

`firmware/core/` is written to be importable under CPython, so the logic is
unit-tested with ordinary `pytest`:

```sh
uv run pytest
```

This runs `tests/test_core.py`, which exercises the device-independent logic
without any hardware.

## Deploying to a device

Connect the device over USB and copy `firmware/` to it (MicroPython runs
`/main.py` at boot):

```sh
uv run mpremote connect auto fs cp -r firmware/ :
uv run mpremote connect auto reset
```

or use the generated task-runner commands (`task deploy`, `just deploy`, ...).
`mpremote connect auto` picks the first USB serial device; use
`mpremote connect list` to see them and pass `port:/dev/ttyACM0` (or `a0`)
to target a specific one.

To iterate on a single file without copying, `mpremote run firmware/main.py`
executes it from RAM.

## Building a distributable firmware image (freeze)

The mpremote flow copies `firmware/` to a device's filesystem. To produce a
**distributable firmware image** — a `.bin`/`.uf2`/`.hex` with your code
*frozen into* the MicroPython firmware — use the `freeze` task:

```sh
task freeze          # or: just freeze / make freeze / poe freeze ...
```

This requires **Docker** (no cross toolchain needed on the host). It:

1. clones a pinned MicroPython source tree into `build/micropython-src/`
   (git-ignored) on first use,
2. freezes `firmware/` into the image via `firmware/manifest.py`
   (`FROZEN_MANIFEST`), running the port build inside the toolchain
   container, and
3. copies the artifact to `dist/`, e.g. `dist/<repo>-rp2-rpi_pico.uf2`.

By default it builds the port you chose when generating the project
(`micropython_port`). Build a different port or board explicitly:

```sh
python tools/micropython/freeze.py --port rp2
python tools/micropython/freeze.py --port esp32 --board ESP32_GENERIC_S3
python tools/micropython/freeze.py --tag vX.Y.Z   # pin the MicroPython version
```

| Port | Toolchain image | Default board | Artifact |
|------|-----------------|---------------|----------|
| esp32 | `espressif/idf` (several GB first pull) | `ESP32_GENERIC` | `firmware.bin` |
| esp8266 | `larsks/esp-open-sdk` | `ESP8266_GENERIC` | `firmware.bin` |
| rp2 | `micropython/build-micropython-arm:bookworm` | `RPI_PICO` | `firmware.uf2` |
| stm32 | `micropython/build-micropython-arm:bookworm` | `PYBV11` | `firmware.dfu` |
| samd | `micropython/build-micropython-arm:bookworm` | `ADAFRUIT_ITSYBITSY_M0_EXPRESS` | `firmware.uf2` |
| mimxrt | `micropython/build-micropython-arm:bookworm` | `MIMXRT1020_EVK` | `firmware.hex` |
| unix | `gcc:12-bookworm` | — | `micropython` (runs on the host) |
| windows | `micropython/build-micropython-win-mingw` | — | `micropython.exe` |

Because the firmware is frozen in, MicroPython runs the frozen `/boot.py` and
`/main.py` at startup exactly like files copied to the device — the same
`firmware/` tree drives both the mpremote development flow and the frozen
release image. The generated CI builds the firmware for your chosen port on
every push and attaches it to GitHub Releases on tag.

> [!NOTE]
> The esp32 image (`espressif/idf`) is several GB and the first build pulls
> MicroPython's ESP-IDF submodules, so the first esp32 freeze is slow. The
> rp2/arm image is much lighter — good for validating the setup.

## Adding a unix-port CI smoke test

The generated CI runs the CPython core tests and type-checks `firmware/`
against the stubs, but does **not** run the firmware itself. To also smoke-run
the code on the MicroPython unix port in CI, add a job that builds the unix
port and runs `main.py`:

```yaml
  unix-smoke:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v7
      - run: sudo apt-get install -y build-essential libffi-dev pkg-config
      - name: Build the unix port
        run: |
          git clone --depth 1 https://github.com/micropython/micropython.git
          make -C micropython/mpy-cross
          make -C micropython/ports/unix
      - name: Run main.py on the unix port
        run: |
          cd firmware
          ../micropython/ports/unix/build-standard/micropython main.py
```

Note the `unix` port has no on-board LED, so `board_config.py` sets
`LED_PIN = None`; the sample `main.py` will raise if it tries to blink on a
port without hardware. Adjust the smoke command to the logic you actually run.
