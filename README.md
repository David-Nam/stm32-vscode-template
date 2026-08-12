# STM32 CMake template

[English](README.md) | [한국어](README_KOR.md)

A VSCode + CMake + Make starting point for STM32 firmware. Point `config.cmake`
at a chip, run one script, and you get a building, flashing, debuggable project
with the HAL and LL drivers pulled straight from STMicroelectronics' GitHub as
submodules.

The sample application prints "Hello, World!" over a UART.

## What it does for you

Set `MCU` (or `BOARD`) and `tools/setup.py` works out the rest:

- which ST repositories hold the CMSIS device headers and the HAL/LL drivers,
  and adds them as submodules
- the flash and RAM origin and size, and the device define (`STM32H743xx`)
- the compiler flags for the core and its FPU

Nothing in the build setup is hardcoded per family. The repository names are
confirmed against GitHub with `git ls-remote`, and the memory map, device
define and core come from the device's CMSIS-Pack. Adding a family that did not
exist when this was written needs no build-system code change.

Verified on five parts spanning four cores, changing nothing but `config.cmake`:

| MCU | Core | Flash | RAM |
|---|---|---|---|
| STM32H743IITx | Cortex-M7, double-precision FPU | 2 MB | 128 KB (DTCM) |
| STM32F411RETx | Cortex-M4F | 512 KB | 128 KB |
| STM32G071RBTx | Cortex-M0+ | 128 KB | 36 KB |
| STM32U575ZITx | Cortex-M33, TrustZone | 2 MB | 768 KB |
| STM32C031C6Tx | Cortex-M0+ | 32 KB | 12 KB |

## Using this GitHub template

Create a new repository from this template for each firmware project. A
template-generated repository is an independent project: it starts with one
commit instead of inheriting this repository's history, is not a fork, and
does not receive later template changes automatically. See GitHub's
[template repository documentation](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-repository-from-a-template).

Use a normal clone of `David-Nam/stm32-vscode-template` only when you intend to
work on the template itself.

### From the GitHub website

1. Open this repository on GitHub.
2. Select **Use this template** > **Create a new repository**.
3. Choose the owner, project name and visibility. Normally leave **Include all
   branches** unchecked: a firmware project only needs the default branch.
4. Select **Create repository from template**.
5. Clone the new repository, including its vendor submodules:

```sh
git clone --recurse-submodules git@github.com:OWNER/PROJECT.git
cd PROJECT
```

If you do select **Include all branches**, GitHub copies them with unrelated
histories, so pull requests and merges between those copied branches are not
available.

If you already cloned without `--recurse-submodules`, initialize them now:

```sh
git submodule update --init --recursive
```

### From the GitHub CLI

The same operation is available through
[`gh repo create`](https://cli.github.com/manual/gh_repo_create):

```sh
gh repo create OWNER/PROJECT \
  --template David-Nam/stm32-vscode-template \
  --private --clone
cd PROJECT
git submodule update --init --recursive
```

Replace `--private` with `--public` when appropriate. `gh repo create --clone`
does not initialize submodules, which is why the last command is still
required.

### First-time project checklist

1. Install the tools in [Requirements](#requirements).
2. Configure the target in `config.cmake`. The file ships with `CoreH743I`
   values as a working example; do not assume they match your board. When
   selecting a known `BOARD`, clear `MCU` so `setup.py` can fill it. When
   selecting `MCU` directly, replace or clear the old `BOARD`. Follow
   [Changing chip or board](#changing-chip-or-board) for the complete reset
   list.
3. Set `ARM_TOOLCHAIN_BIN`, and update the duplicate debugger paths in
   `.vscode/settings.json` if you use VSCode.
4. Run `python3 tools/setup.py`, then `make`.
5. If you use OpenOCD on a non-H7 target, replace `target/stm32h7x.cfg` in
   `.vscode/launch.json` with the target configuration for that family.
6. Replace this README's title and overview with information about the new
   firmware project, keeping whichever setup notes its users still need.
7. Optionally rename `project(stm32-template ...)` in `CMakeLists.txt`. If you
   do, also change the `.elf` paths in `.vscode/launch.json`.
8. Commit the configured `config.cmake`, `.gitmodules`, submodule entries and
   generated family HAL configuration under `inc/` as part of your project.

Template updates are not synced into generated repositories. Treat this as a
starting snapshot. If you later want to inspect changes, add the template as a
separate remote and copy or cherry-pick only the changes you need; merging the
branches directly is usually unhelpful because their histories are unrelated.

## Requirements

The commands below target macOS on Apple silicon. The CMake project itself can
be used on other hosts, but install equivalent versions of Git, Python 3,
CMake, Make, the Arm GNU Toolchain and your debug probe tools, then update the
toolchain/debugger paths. On Windows, WSL or another Unix-like shell is the
least-friction path for the supplied `Makefile` and shell helper.

**Arm GNU Toolchain.** Homebrew's `arm-none-eabi-gcc` will not do: it ships
without newlib, so `printf` does not link. Use an official Arm release.

```sh
brew install --cask gcc-arm-embedded          # needs sudo for the .pkg
```

or, without sudo, unpack the tarball of the same release:

```sh
mkdir -p ~/.local/opt && cd ~/.local/opt
V=15.3.rel1
curl -LO "https://gitlab.arm.com/api/v4/projects/tooling%2Fgnu-toolchains-for-arm/packages/generic/gnu-toolchain/$V/arm-gnu-toolchain-$V-darwin-arm64-arm-none-eabi.tar.xz"
tar xf arm-gnu-toolchain-$V-darwin-arm64-arm-none-eabi.tar.xz
```

Then point `ARM_TOOLCHAIN_BIN` in `config.cmake` at its `bin` directory, or add
that directory to `PATH` and leave the variable empty.

**Everything else:**

```sh
brew install cmake stlink       # stlink gives you st-flash and st-util
brew install open-ocd           # optional, only for OpenOCD debugging
code --install-extension marus25.cortex-debug
```

`python3`, `git` and `make` are also required. The first `setup.py` run needs
network access to inspect ST repositories, download the CMSIS-Pack data and
fetch submodules. Builds are offline after setup.

## Quick start

```sh
git clone --recurse-submodules <your generated repo URL> PROJECT
cd PROJECT
$EDITOR config.cmake            # replace the example BOARD/MCU and console values
python3 tools/setup.py          # fetch submodules, fill in the derived values
make                            # build
make flash                      # write it to the chip with st-flash
```

Then open a serial terminal on the console UART at 115200 8N1 and reset the
board:

```sh
ls /dev/tty.*
screen /dev/tty.usbserial-XXXX 115200      # quit with Ctrl-A K
```

```
Hello, World!
board  CoreH743I (STM32H743IITx)
sysclk 64000000 Hz, pclk1 64000000 Hz
tick: 1
tick: 2
```

## config.cmake

This is the only file you should need to edit. Some values you set, the rest
`tools/setup.py` fills in. It only ever writes a value that is **empty**, so
anything you put there by hand survives. To have a derived value recomputed,
blank it and run `setup.py` again.

### Toolchain

| Variable | Who sets it | Meaning |
|---|---|---|
| `ARM_TOOLCHAIN_BIN` | you | `bin` directory of the Arm toolchain. Leave empty to use whatever `arm-none-eabi-gcc` is on `PATH`. |

### Target

| Variable | Who sets it | Meaning |
|---|---|---|
| `BOARD` | you | A name from `setup.py --list-boards`, or free text. If `MCU` is empty, a known board fills in `MCU` and the console pins. |
| `MCU` | you, or from `BOARD` | Full part number, e.g. `STM32H743IITx`. A trailing temperature-grade digit is fine (`STM32H743IIT6`). |

Setting `MCU` directly works for any STM32; the board table is only a shortcut
for a handful of boards.

### Memory

All four are filled from the CMSIS-Pack. You normally never touch them.

| Variable | Meaning |
|---|---|
| `FLASH_ORIGIN` | Usually `0x08000000`. Change it to place the application behind a bootloader. |
| `FLASH_SIZE` | Contiguous flash. Abutting banks are merged, so an STM32H743's two 1 MB banks come out as `2048K`. |
| `RAM_ORIGIN` | Start of the RAM block the linker script uses. |
| `RAM_SIZE` | Its size. Abutting regions are merged, so an STM32U575's SRAM1+2+3 come out as `768K`. |
| `RAM_REGION` | Empty picks whatever the pack puts at `0x20000000`. Name a region to override. |

`RAM_REGION` is worth understanding. The default is *not* the largest region:
on an STM32H743 the pack lists `DTCMRAM` (128K), `RAM_D1` (512K), `RAM_D2`
(288K) and `RAM_D3` (64K), and picking the biggest would be wrong more often
than right. Whatever sits at `0x20000000` is TCM or main SRAM on every STM32 and
is usable straight out of reset, whereas `RAM_D2` and `RAM_D3` need their RCC
clocks enabled first and will hang the program if you jump straight into them.
`setup.py` prints every region it found, so:

```cmake
set(RAM_REGION "RAM_D1")     # then blank RAM_ORIGIN and RAM_SIZE, re-run setup.py
```

### Console

Which UART reaches a USB-serial bridge is board wiring, so nothing can derive
it. `setup.py pins` lists what the chip offers, with the alternate-function
numbers that are otherwise a datasheet hunt:

```
$ python3 tools/setup.py pins UART4
  UART4      TX PA0(AF8) PA12(AF6) PB9(AF8) PC10(AF8) PD1(AF8) PH13(AF8)
             RX PA1(AF8) PA11(AF6) PB8(AF8) PC11(AF8) PD0(AF8) PH14(AF8) PI9(AF8)
```

Pick a TX/RX pair that shares an AF number. Note the AF is per pin, not per
peripheral: UART4 is AF8 on PH13 but AF6 on PA12.

| Variable | Meaning |
|---|---|
| `CONSOLE_UART` | Peripheral instance, e.g. `UART4`, `USART2`, `LPUART1`. |
| `CONSOLE_TX` / `CONSOLE_RX` | Pins as `P<port><number>`, e.g. `PH13`. |
| `CONSOLE_AF` | Alternate-function number only, e.g. `8`. `board.h` turns it into `GPIO_AF8_UART4`. |
| `CONSOLE_BAUD` | Default 115200. The HAL computes the divisor from the live PCLK, so it stays right if you add a PLL. |

### Board clocks

| Variable | Meaning |
|---|---|
| `HSE_HZ` | Crystal fitted on the board. Reaches the HAL as `HSE_VALUE`. |

This is a board property, so the CMSIS-Pack does not know it, and the HAL
header's default is a guess (25 MHz for STM32H7). Nothing uses it until you
write a `SystemClock_Config`, at which point a wrong value produces a wrong
system clock and a garbled console.

### Device

| Variable | Meaning |
|---|---|
| `FAMILY` | `H7`, `G0`, ... Picks the submodule directory names. |
| `DEVICE_DEFINE` | e.g. `STM32H743xx`. Selects the CMSIS header and the startup file. |
| `CPU_FLAGS` | e.g. `-mcpu=cortex-m7 -mthumb -mfpu=fpv5-d16 -mfloat-abi=hard`. |

All three come from the pack. Override `CPU_FLAGS` by hand if you need
something unusual.

### Extra libraries

| Variable | Meaning |
|---|---|
| `EXTRA_LIB_DIRS` | Directories to compile in. Each is scanned for `*.c`, and its `Inc`/`Include` is added to the include path. Maintained by `setup.py add`. |

### Writing rules

`tools/setup.py` both reads and rewrites this file with a line-oriented parser,
so it needs plain single-line `set()` calls:

- one `set()` per line, never split across lines
- no `)` inside a value
- no `if()` / `foreach()` — the parser reads every `set()` flat and would
  misread conditionals
- trailing `#` comments are fine and are preserved when a value is rewritten
- empty is `set(X "")` or `set(X)`
- CMake expressions such as `$ENV{HOME}` are fine; `setup.py` passes them
  through untouched and CMake expands them

## Changing chip or board

`config.cmake` starts as a working `CoreH743I` example. To select a known board
from `setup.py --list-boards`, set `BOARD`, blank `MCU`, and blank the console
and derived fields. `setup.py` only fills board defaults when `MCU` is empty:

```cmake
set(BOARD "NUCLEO-F411RE")
set(MCU "")
set(FLASH_ORIGIN "")
set(FLASH_SIZE "")
set(RAM_ORIGIN "")
set(RAM_SIZE "")
set(RAM_REGION "")
set(FAMILY "")
set(DEVICE_DEFINE "")
set(CPU_FLAGS "")
set(CONSOLE_UART "")
set(CONSOLE_TX "")
set(CONSOLE_RX "")
set(CONSOLE_AF "")
```

To configure an MCU directly, set `MCU`, replace `BOARD` with a descriptive
name or leave it empty, blank the same derived fields, and set the console
fields yourself after checking `setup.py pins`. In both cases, review
`HSE_HZ`: it is a board property and `setup.py` deliberately cannot derive it.

Then regenerate and build:

```sh
python3 tools/setup.py          # fetches the new family, refills the blanks
python3 tools/setup.py pins     # inspect or verify console pin choices
make clean && make
```

The old family's submodules stay behind; remove them if you are not coming back
(see below).

`tools/try_board.sh` does all of this in a throwaway copy, which is the quickest
way to check a chip before committing to it:

```sh
tools/try_board.sh NUCLEO-F411RE
tools/try_board.sh "" STM32G071RBTx
```

## Adding libraries

Examples, BSP and middleware are not fetched by default because they are large
and most projects want none of them.

```sh
python3 tools/setup.py add cube                 # the whole STM32Cube<FAM> repo, shallow
python3 tools/setup.py add https://github.com/STMicroelectronics/stm32h7xx-nucleo-bsp
```

Each lands in `lib/` and is appended to `EXTRA_LIB_DIRS`, after which its `*.c`
files are compiled and its `Inc`/`Include` is on the include path.

To remove one:

```sh
git rm lib/<name>          # not --cached: that leaves the .gitmodules entry behind
```

then drop it from `EXTRA_LIB_DIRS`.

## Build, flash, debug

```sh
make                # configure if needed, then build
make clean
make flash          # st-flash --reset write build/stm32-template.bin <FLASH_ORIGIN>
```

Output lands in `build/`: `.elf`, `.hex`, `.bin`, `.map`, the generated linker
script, and `compile_commands.json`.

The default build type is `Debug`. Without it CMake passes neither `-O` nor
`-g` and the debugger cannot see a single variable.

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=MinSizeRel     # 11 KB instead of 16 KB
```

`-g` does not carry macro definitions, so `print GPIO_PIN_13` in gdb fails. If
you want that, build with `-DCMAKE_C_FLAGS_DEBUG="-g3 -O0"`.

### VSCode

Tasks: **build** (the default build task), **clean**, **flash**, **setup**.

Debugging needs the Cortex-Debug extension. F5 offers:

- **Debug (st-util)** — no extra install, `st-util` comes with `stlink`
- **Debug (OpenOCD)** — needs `brew install open-ocd`
- **Attach (st-util, no reset)** — connect to a running target without
  reprogramming it

Both launch configurations rebuild and reprogram before stopping at `main`.

The supplied OpenOCD launch configuration uses `target/stm32h7x.cfg`. Change
that file name when the selected target is not an STM32H7. The `st-util`
configuration does not contain this family-specific setting.

`.vscode/settings.json` repeats the toolchain path that `config.cmake` already
has, in `cortex-debug.armToolchainPath` and `cortex-debug.gdbPath`. VSCode
settings cannot read a CMake file, so if you move the toolchain, fix both.

## How the application is put together

`src/main.c` never names a family, a port or a pin. `cmake/board.h.in` is
generated into `build/board.h` from `config.cmake`:

```c
#include "stm32h7xx_hal.h"
#define CONSOLE_UART              UART4
#define CONSOLE_AF                GPIO_AF8_UART4
#define CONSOLE_TX_PORT           GPIOH
#define CONSOLE_TX_PIN            GPIO_PIN_13
#define CONSOLE_TX_CLK_ENABLE()   __HAL_RCC_GPIOH_CLK_ENABLE()
```

Both driver sets are compiled and `--gc-sections` discards what you do not
call — 123 HAL and LL objects go in, and the sample links 14 symbols out of
them. Include the LL headers you want directly:

```c
#include "stm32h7xx_ll_gpio.h"
```

`USE_HAL_DRIVER` and `USE_FULL_LL_DRIVER` are both defined.

### Things the sample does deliberately

**No PLL.** It runs on the reset clock, which on an STM32H743 is HSI at 64 MHz.
The clock tree differs on every STM32, so the reset state is the one setting
that boots everywhere. Write your own `SystemClock_Config` when you need speed;
`HSE_HZ` is correct for the shipped `CoreH743I` example, but must be reviewed
for your board.

**`SysTick_Handler` in `main.c`.** The CMSIS startup file aliases every handler
to `Default_Handler`, an infinite loop, and the HAL expects the project to call
`HAL_IncTick`. Without it the first `HAL_Delay` never returns. Add your other
interrupt handlers alongside it.

**`setvbuf(stdout, NULL, _IONBF, 0)`.** newlib asks `_isatty` whether stdout is
a terminal, `nosys` says no, and stdout would then be fully buffered — nothing
appears until a kilobyte has piled up. Unbuffered also means a line cut short by
a fault still shows the part that got out.

**`tick` and `startup_error` are file-scope and `volatile`.** When the console
is silent there is nothing to blink, so these are what you read in a debugger to
tell "not running" from "running but the UART is wrong".

## Where the data comes from

| What | Source |
|---|---|
| CMSIS core | `github.com/STMicroelectronics/cmsis-core` |
| Device headers, startup | `github.com/STMicroelectronics/cmsis-device-<fam>` |
| HAL and LL drivers | `github.com/STMicroelectronics/stm32<fam>xx-hal-driver` |
| Memory map, device define, core/FPU | `keil.com/pack/Keil.STM32<FAM>xx_DFP.pdsc` |
| Console pin and AF candidates | `github.com/STMicroelectronics/STM32_open_pin_data` |

The last two are only read by `setup.py`, and what it finds is written into
`config.cmake`. Builds need no network.

The CMSIS headers are not enough on their own: they carry base addresses but
not sizes, and their `FLASH_SIZE` is a runtime read of the flash size register,
which a linker cannot use. `FLASH_END` is the device *line* maximum, so the
STM32H723 header claims 1 MB even on the 512 KB parts. ST ships ready-made
linker scripts for only a few families. The CMSIS-Pack has the real per-device
map, which is where CubeMX gets it too.

## Limits

- `setup.py` derives flash size from the part number only as an offline
  fallback, and that fallback does not understand STM32H7RS or STM32N6 naming.
  With the pack reachable this never comes up.
- The board table has four entries. Any other board means setting `MCU` and the
  console pins yourself; `setup.py pins` covers the tedious half.
- One RAM region reaches the linker script. Using an STM32H7's other SRAMs, or
  its external SDRAM, means adding them to `cmake/stm32_flash.ld.in` yourself.
- `.vscode/*.json` gets rewritten by VSCode extensions without asking. The
  C/C++ extension will append a host-clang task and steal the default build
  task if you press the Run button on a C file; `C_Cpp.debugShortcut` is off
  here for that reason. Check `git diff` before committing.

## License

This repository does not currently declare a project license. Before inviting
others to use, modify or redistribute this template, choose a license and add a
`LICENSE` file. Each STMicroelectronics submodule remains governed by the
license in that upstream repository; a project-level license does not replace
those vendor licenses.
