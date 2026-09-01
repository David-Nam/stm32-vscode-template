# STM32 CMake template

[English](README.md) | [한국어](README_KOR.md)

A VSCode + CMake + Ninja starting point for STM32 firmware. Select a chip with
`tools/setup.py target`, and you get a building, flashing, debuggable project
with the HAL and LL drivers pulled straight from STMicroelectronics' GitHub as
submodules.

The sample application prints "Hello, World!" over a UART, from a FreeRTOS task.

## What it does for you

Give `tools/setup.py target` an MCU or known board and it works out the rest:

- which ST repositories hold the CMSIS device headers and the HAL/LL drivers,
  and adds them as submodules
- the flash and RAM origin and size, and the device define (`STM32H743xx`)
- the compiler flags for the core and its FPU

Nothing in the build setup is hardcoded per family. The repository names are
confirmed against GitHub with `git ls-remote`, and the memory map, device
define and core come from the device's CMSIS-Pack. Adding a family that did not
exist when this was written needs no build-system code change.

FreeRTOS comes with it. `RTOS` in `config.cmake` picks `freertos` (the default)
or `none`, the kernel port follows from the core the same way the compiler flags
do, and `app/main.c` runs its "Hello, World!" from a task. See
[RTOS](#rtos).

The only vendor code committed here is `lib/cmsis-core` and `lib/freertos-kernel`,
neither of which depends on the family. The device headers, the HAL/LL drivers
and the family's `stm32<fam>xx_hal_conf.h` under `inc/` all arrive when you run
`setup.py`, so a new project never carries another chip's drivers around.

Verified on five parts spanning four cores through the same target workflow:

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
work on the template itself. Running `setup.py` in such a clone adds
`lib/cmsis-device-<fam>`, `lib/stm32<fam>xx-hal-driver` and a
`stm32<fam>xx_hal_conf.h`: those belong to a project, not to the template, so
keep them out of template commits.

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

1. Install the tools in [Requirements](#requirements), then confirm the machine
   is ready with `python3 tools/setup.py doctor`.
2. Select a target atomically. The repository ships with `CoreH743I` as a
   working example; do not assume it matches your board. Run
   `python3 tools/setup.py target --board <name>` for a listed board or
   `python3 tools/setup.py target --mcu <part>` for an MCU.
3. Make `arm-none-eabi-gcc` reachable: on `PATH`, or through
   `ARM_TOOLCHAIN_BIN`. `setup.py doctor --fix` fills both `config.cmake` and
   `.vscode/settings.json` in when it finds a toolchain that `PATH` misses.
4. The target command fetches the required family dependencies. Then run
   `cmake --preset default` and
   `cmake --build --preset default`.
5. If you use OpenOCD on a non-H7 target, replace `target/stm32h7x.cfg` in
   `.vscode/launch.json` with the target configuration for that family.
6. Replace this README's title and overview with information about the new
   firmware project, keeping whichever setup notes its users still need.
   `CLAUDE.md` describes maintaining the template, not your project: replace it
   with your own notes or delete it.
7. Optionally rename `project(stm32-template ...)` in `CMakeLists.txt`. If you
   do, also change the `.elf` paths in `.vscode/launch.json`.
8. Replace `LICENSE` with your project's own, or delete it if the project is
   not published. The template is MIT; a repository generated from it is
   yours, and the vendor submodules keep their own licenses either way.
9. Commit `config.cmake`, `generated/device.cmake`, `.gitmodules`, submodule
   entries and the generated family HAL configuration under `inc/` as part of
   your project.

Template updates are not synced into generated repositories. Treat this as a
starting snapshot. If you later want to inspect changes, add the template as a
separate remote and copy or cherry-pick only the changes you need; merging the
branches directly is usually unhelpful because their histories are unrelated.

## Requirements

macOS, Linux and Windows all need the same six things: Git, Python 3, CMake
3.21 or newer, Ninja, the Arm GNU Toolchain, and the tools for your debug
probe. There is no Makefile and no shell script in the build path — every
command below is the same on all three hosts.

**Arm GNU Toolchain.** Homebrew's `arm-none-eabi-gcc` will not do: it ships
without newlib, so `printf` does not link. Use an official
[Arm release](https://developer.arm.com/downloads/-/arm-gnu-toolchain-downloads).

macOS:

```sh
brew install --cask gcc-arm-embedded    # needs sudo for the .pkg
brew install cmake ninja stlink         # stlink gives you st-flash and st-util
brew install open-ocd                   # optional, only for OpenOCD debugging
```

or, without sudo, unpack the tarball of the same release:

```sh
mkdir -p ~/.local/opt && cd ~/.local/opt
V=15.3.rel1
curl -LO "https://gitlab.arm.com/api/v4/projects/tooling%2Fgnu-toolchains-for-arm/packages/generic/gnu-toolchain/$V/arm-gnu-toolchain-$V-darwin-arm64-arm-none-eabi.tar.xz"
tar xf arm-gnu-toolchain-$V-darwin-arm64-arm-none-eabi.tar.xz
```

Linux (Debian/Ubuntu; the tarball above works too, with the
`x86_64-arm-none-eabi` build):

```sh
sudo apt install git python3 cmake ninja-build stlink-tools
sudo apt install openocd                # optional
```

Windows: install Git, Python 3, CMake and Ninja (`winget`, Chocolatey or the
official installers), and the Arm toolchain from the link above. Tick the
installer's "Add path to environment variable" box — the default install
directory contains `Program Files (x86)`, and a `)` inside a `set()` value is
one of the few things `config.cmake` cannot carry. `st-flash`/`st-util` come
from the [stlink releases](https://github.com/stlink-org/stlink/releases).
PowerShell and cmd are both fine; WSL works but is not required.

**Pointing CMake at the toolchain.** In order of preference: put its `bin`
directory on `PATH` and leave `ARM_TOOLCHAIN_BIN` empty, or export
`ARM_TOOLCHAIN_BIN` as an environment variable, or set it in `config.cmake`.
The environment variable is the one to use when you do not want your own paths
in a committed file.

VSCode users also want the debugger extension:

```sh
code --install-extension marus25.cortex-debug
```

**Checking the machine.** `setup.py doctor` answers "is this host ready?"
without building anything: it detects the OS, looks for each tool, verifies
that CMake is new enough and that the toolchain actually ships newlib, and
prints the install command for whatever is missing. It exits non-zero when a
tool the build needs is absent, so CI can use it too.

```sh
python3 tools/setup.py doctor           # report only
python3 tools/setup.py doctor --fix     # also record an off-PATH toolchain
```

If the toolchain is installed somewhere `PATH` does not reach, `doctor` finds
it in the usual install directories for the host and `--fix` writes that path
into `config.cmake` and `.vscode/settings.json` for you. The write needs
`--fix` because both files are committed; a plain `doctor` never edits
anything. It installs nothing and never touches `PATH`, your shell profile or
the registry — those stay yours.

The first `setup.py` run needs network access to inspect ST repositories,
download the CMSIS-Pack data and fetch submodules. Builds are offline after
setup.

## Quick start

```sh
git clone --recurse-submodules <your generated repo URL> PROJECT
cd PROJECT
python3 tools/setup.py target --board NUCLEO-F411RE  # target + dependencies
$EDITOR config.cmake                    # optional: RTOS, console or explicit overrides
cmake --preset default                  # configure, once
cmake --build --preset default          # build
cmake --build --preset flash            # write it to the chip with st-flash
```

On Windows the interpreter is `python`, not `python3`; the three `cmake` lines
are identical everywhere.

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

This is the user-owned configuration for project policy, the console and
explicit overrides. Do not change `BOARD` and `MCU` independently: the target
command updates them together and writes Pack-derived facts to
`generated/device.cmake`. CMake checks the identities in both files and stops
if they do not match.

### Toolchain

| Variable | Who sets it | Meaning |
|---|---|---|
| `ARM_TOOLCHAIN_BIN` | you | `bin` directory of the Arm toolchain. Ships empty, which means "use whatever `arm-none-eabi-gcc` is on `PATH`". An environment variable of the same name is also honoured and keeps your own path out of the repository. Forward slashes on every host, and no `)` in the value. |

### Target

| Variable | Who sets it | Meaning |
|---|---|---|
| `BOARD` | `setup.py target --board` | A name from `setup.py --list-boards`; the command also selects its MCU, console pins and HSE. |
| `MCU` | `setup.py target` | Full part number, e.g. `STM32H743IITx`. `--mcu` clears board-specific console and clock values. |
| `RAM_REGION` | `setup.py target --ram-region` | Optional named Pack RAM region; empty selects the safe region at `0x20000000`. |

Do not edit one without the other. A known BOARD/MCU mismatch fails before any
network, file or submodule operation.

### Memory

The physical values below live in generated/device.cmake and come from the
CMSIS-Pack. Do not edit that file; re-run the target command instead.

| Variable | Meaning |
|---|---|
| `FLASH_ORIGIN` | Physical Flash start, usually `0x08000000`. |
| `FLASH_SIZE` | Contiguous flash. Abutting banks are merged, so an STM32H743's two 1 MB banks come out as `2048K`. |
| `RAM_ORIGIN` | Start of the RAM block the linker script uses. |
| `RAM_SIZE` | Its size. Abutting regions are merged, so an STM32U575's SRAM1+2+3 come out as `768K`. |
| `STM32_RAM_REGION` | Name of the Pack region selected by setup. |

`RAM_REGION` is worth understanding. The default is *not* the largest region:
on an STM32H743 the pack lists `DTCMRAM` (128K), `RAM_D1` (512K), `RAM_D2`
(288K) and `RAM_D3` (64K), and picking the biggest would be wrong more often
than right. Whatever sits at `0x20000000` is TCM or main SRAM on every STM32 and
is usable straight out of reset, whereas `RAM_D2` and `RAM_D3` need their RCC
clocks enabled first and will hang the program if you jump straight into them.
`setup.py` prints every region it found. Select a listed region as part of the
same atomic target operation:

```sh
python3 tools/setup.py target --board CoreH743I --ram-region RAM_D1
```

Other deliberate departures from Pack data use clearly named
`TARGET_*_OVERRIDE` variables in `config.cmake`; a retarget clears them so an
override cannot leak to another MCU.

```cmake
set(TARGET_RAM_ORIGIN_OVERRIDE "0x24000000")
set(TARGET_RAM_SIZE_OVERRIDE "512K")
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

These are read-only facts in `generated/device.cmake`, not settings to maintain
by hand:

| Variable | Meaning |
|---|---|
| `FAMILY` | `H7`, `G0`, ... Picks the submodule directory names. |
| `DEVICE_DEFINE` | e.g. `STM32H743xx`. Selects the CMSIS header and the startup file. |
| `PROCESSOR_CORE` / `PROCESSOR_FPU` | Processor properties selected from the Pack record. |
| `CPU_FLAGS` | e.g. `-mcpu=cortex-m7 -mthumb -mfpu=fpv5-d16 -mfloat-abi=hard`. |
| `STM32_PACK_*` | URL, vendor, Pack name/version and the exact part record used to derive this file. |

Re-run `setup.py target` to regenerate them. If a project deliberately needs
different compiler flags, set `TARGET_CPU_FLAGS_OVERRIDE` in `config.cmake`;
the next retarget clears that override.

### RTOS

| Variable | Meaning |
|---|---|
| `RTOS` | `freertos` (the default) or `none` for a bare `main` loop. |
| `FREERTOS_HEAP_KB` | Size of the one `heap_4` array every task stack, queue and timer comes out of. |

`setup.py` checks out `lib/freertos-kernel`; the build picks the port out of
`CPU_FLAGS` on its own — `ARM_CM7/r0p1`, `ARM_CM4F`, `ARM_CM3`, `ARM_CM0`, or the
non-TrustZone ARMv8-M port for M23/M33/M55/M85. The configure step prints which
one it took.

`cmake/FreeRTOSConfig.h.in` is generated into `build/FreeRTOSConfig.h` the same
way `board.h` is, so the heap size and the per-device priority bits follow
`config.cmake` instead of being pasted per project. Turn options on there.

The kernel owns `SysTick`, and `main.c` hangs `HAL_IncTick` on the tick hook, so
`HAL_Delay` and every HAL timeout keep working inside tasks. Between `HAL_Init`
and `vTaskStartScheduler` nothing ticks: init that has to wait belongs in a task.

Another RTOS is a `cmake/rtos-<name>.cmake` that appends to `STM32_SOURCES`,
`STM32_INCLUDES` and `STM32_DEFINES`, plus that name in `RTOS`. `CMakeLists.txt`
includes whatever `RTOS` names and nothing else looks at it. Only FreeRTOS ships
with the template.

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

`config.cmake` starts as a working `CoreH743I` example. Replace it with one
command rather than editing and clearing a list of related values:

```sh
python3 tools/setup.py --list-boards
python3 tools/setup.py target --board NUCLEO-F411RE
cmake --preset default && cmake --build --preset default
```

Not every STM32 can be selected: multi-core parts, flashless parts and a few
others are refused. [docs/unsupported-mcu.md](docs/unsupported-mcu.md) lists
them and says how each one is detected.

For an unlisted board, select the MCU directly and then configure board wiring:

```sh
python3 tools/setup.py target --mcu STM32G071RBTx
python3 tools/setup.py pins USART2
$EDITOR config.cmake             # console pins and HSE_HZ
cmake --preset default && cmake --build --preset default
```

The command resolves and validates the complete Pack record before replacing
either target file. It writes user intent to `config.cmake` and physical
device/core facts plus Pack provenance to `generated/device.cmake`. A failed
network lookup or dependency setup leaves both target files unchanged. Old
family submodules stay behind and the command reports them; remove them only
after the new target has been verified.

`tools/try_board.py` does all of this in a throwaway copy, which is the quickest
way to check a chip before committing to it:

```sh
python3 tools/try_board.py NUCLEO-F411RE
```

Each run uses a new, uniquely named directory below the system temporary
directory and removes only that owned directory when it exits. Use `--keep` to
preserve the copy for inspection, or set `TRY_DIR` to an existing directory to
choose its parent. The safe default copies tracked files only; use
`--include-untracked` when a test deliberately needs current untracked files.
`--flash` builds and programs the named board through the connected ST-LINK.
Before creating the copy or downloading dependencies, the helper checks Git,
CMake, Ninja, the Arm toolchain and, for `--flash`, `st-flash`. It reuses
`setup.py doctor`'s OS-specific search and passes a discovered off-PATH Arm
toolchain to every child command automatically; no manual export is needed.
This helper accepts complete board entries only; for an unlisted board, use the
MCU workflow above and provide its console wiring before building.

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
cmake --preset default                          # configure; only after config.cmake changes
cmake --build --preset default                  # build
cmake --build --preset default --target clean   # or delete build/ for a full reset
cmake --build --preset flash                    # st-flash --reset write build/stm32-template.bin <FLASH_ORIGIN>
```

`CMakePresets.json` holds the generator (Ninja), the build directory and the
toolchain file, which is what keeps the commands identical on the three hosts.
Output lands in `build/`: `.elf`, `.hex`, `.bin`, `.map`, the generated linker
script, and `compile_commands.json`.

The default build type is `Debug`. Without it CMake passes neither `-O` nor
`-g` and the debugger cannot see a single variable.

```sh
cmake --preset default -DCMAKE_BUILD_TYPE=MinSizeRel     # 11 KB instead of 16 KB
```

`-g` does not carry macro definitions, so `print GPIO_PIN_13` in gdb fails. If
you want that, build with `-DCMAKE_C_FLAGS_DEBUG="-g3 -O0"`.

### VSCode

Tasks: **build** (the default build task, and it configures first), **clean**,
**flash**, **setup**. They call the same `cmake --preset` commands as the shell,
so they work on all three hosts; the **setup** task is the only one with a
Windows variant, because the interpreter is `python` there.

Debugging needs the Cortex-Debug extension. F5 offers:

- **Debug (st-util)** — no extra install, `st-util` comes with `stlink`
- **Debug (OpenOCD)** — needs OpenOCD installed
- **Attach (st-util, no reset)** — connect to a running target without
  reprogramming it

Both launch configurations rebuild and reprogram before stopping at `main`.

The supplied OpenOCD launch configuration uses `target/stm32h7x.cfg`. Change
that file name when the selected target is not an STM32H7. The `st-util`
configuration does not contain this family-specific setting.

Cortex-Debug finds `arm-none-eabi-gdb` on `PATH`. If yours is not there, set
`cortex-debug.armToolchainPath` in `.vscode/settings.json`, where it is left
commented out with an example: VSCode settings cannot read a CMake file, so
this path is separate from `ARM_TOOLCHAIN_BIN` and has to be kept in step by
hand.

## How the application is put together

`app/main.c` never names a family, a port or a pin. `cmake/board.h.in` is
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
interrupt handlers alongside it. With `RTOS=freertos` the kernel owns that
vector instead and `vApplicationTickHook` makes the call.

**One task, and it is the one that prints.** newlib's `printf` is not reentrant
here, so a second task calling it needs a mutex around every call. The task
prints `xPortGetFreeHeapSize` next to the tick count: that is the number to
watch when `FREERTOS_HEAP_KB` needs raising.

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
| FreeRTOS kernel | `github.com/FreeRTOS/FreeRTOS-Kernel` |
| Device headers, startup | `github.com/STMicroelectronics/cmsis-device-<fam>` |
| HAL and LL drivers | `github.com/STMicroelectronics/stm32<fam>xx-hal-driver` |
| Memory map, device define, core/FPU | `keil.com/pack/Keil.STM32<FAM>xx_DFP.pdsc` |
| Console pin and AF candidates | `github.com/STMicroelectronics/STM32_open_pin_data` |

The last two are only read by `setup.py`. Device facts and Pack provenance are
written into `generated/device.cmake`; user policy remains in `config.cmake`.
Builds need no network.

The CMSIS headers are not enough on their own: they carry base addresses but
not sizes, and their `FLASH_SIZE` is a runtime read of the flash size register,
which a linker cannot use. `FLASH_END` is the device *line* maximum, so the
STM32H723 header claims 1 MB even on the 512 KB parts. ST ships ready-made
linker scripts for only a few families. The CMSIS-Pack has the real per-device
map, which is where CubeMX gets it too.

## Limits

- A target change requires a reachable CMSIS-Pack. It fails without replacing
  the current target files rather than generating an incomplete memory map.
- The board table has four entries. Any other board means setting `MCU` and the
  console pins yourself; `setup.py pins` covers the tedious half.
- One RAM region reaches the linker script. Using an STM32H7's other SRAMs, or
  its external SDRAM, means adding them to `cmake/stm32_flash.ld.in` yourself.
- `.vscode/*.json` gets rewritten by VSCode extensions without asking. The
  C/C++ extension will append a host-clang task and steal the default build
  task if you press the Run button on a C file; `C_Cpp.debugShortcut` is off
  here for that reason. Check `git diff` before committing.
- The console pins for `CoreH743I` are the ones this template was tested with
  on an external USB-serial adapter, not an on-board bridge. The NUCLEO entries
  are the UART their ST-LINK exposes as a virtual COM port.
- FreeRTOS is wired up as one non-TrustZone, no-MPU image. A TrustZone project
  wants the plain `ARM_CM33` port and a secure image of its own, which is a
  project rather than a switch in `config.cmake`.

## License

MIT, see [LICENSE](LICENSE). Use it in commercial work if you like; the only
condition is that the copyright notice travels with the copies you distribute.

This covers the template itself. Each submodule under `lib/` — the
STMicroelectronics ones and `freertos-kernel`, which is MIT as well — remains
governed by the license in its own upstream repository, and a project-level
license does not replace those vendor licenses.
