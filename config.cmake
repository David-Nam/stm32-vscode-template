# Project configuration. This is the only file you should need to edit.
# After changing MCU or BOARD, run tools/setup.py
# (python3 tools/setup.py on macOS and Linux, python tools/setup.py on Windows)
#
# tools/setup.py both reads and rewrites this file, so keep it to plain
# single-line set() calls: one per line, no if()/foreach(), and no ')' inside
# a value. Trailing '#' comments are fine and are preserved on rewrite.
# setup.py only ever writes MCU, CONSOLE_*, RAM_*, FLASH_SIZE (and only when
# they are empty) plus EXTRA_LIB_DIRS. Everything else it just reads.

# --- Toolchain -------------------------------------------------------------
# Empty means "use whatever arm-none-eabi-gcc is on PATH", which is right when
# the toolchain was installed by a package manager. Fill it in only when the
# toolchain lives somewhere PATH does not reach. Forward slashes on every host,
# Windows included, and no ')' anywhere in the value -- setup.py's parser stops
# at the first one. Examples:
#
#   macOS / Linux, unpacked tarball
#     set(ARM_TOOLCHAIN_BIN "$ENV{HOME}/.local/opt/arm-gnu-toolchain-14.3.rel1-arm-none-eabi/bin")
#   Windows, Arm GNU Toolchain installer (default path has parentheses, so
#   install it somewhere else or use the 8.3 short path C:/PROGRA~2/...)
#     set(ARM_TOOLCHAIN_BIN "C:/arm-gnu-toolchain/14.3 rel1/bin")
#
# Note: Homebrew's arm-none-eabi-gcc ships without newlib, so printf will not
# link against it. Use an Arm GNU Toolchain release instead.
set(ARM_TOOLCHAIN_BIN "")

# --- Target ----------------------------------------------------------------
# Set BOARD to a name from `tools/setup.py --list-boards`, or leave it empty
# and set MCU directly. setup.py fills in whatever is left empty below.
set(BOARD "CoreH743I")
set(MCU "STM32H743IITx")

# --- Memory ----------------------------------------------------------------
# Filled in by setup.py from the device's CMSIS-Pack. Do not hand-edit unless
# you mean to override; setup.py only writes values that are still empty.
# Clear a value and re-run setup.py to have it re-derived.
set(FLASH_ORIGIN "0x08000000")
set(FLASH_SIZE "2048K")
set(RAM_ORIGIN "0x20000000")
set(RAM_SIZE "128K")

# RAM defaults to whatever the pack puts at 0x20000000, which is TCM or main
# SRAM on every STM32 and works straight out of reset. Name a different region
# here to use it instead -- setup.py prints the available names.
# On STM32H743 the choices are DTCMRAM (128K, the default), RAM_D1 (512K),
# RAM_D2 (288K) and RAM_D3 (64K). RAM_D2 and RAM_D3 need their RCC clocks
# enabled before first access, so do not point at them without adding that.
set(RAM_REGION "")

# --- Device (filled in by setup.py from the CMSIS-Pack) --------------------
set(FAMILY "H7")
set(DEVICE_DEFINE "STM32H743xx")
set(CPU_FLAGS "-mcpu=cortex-m7" "-mthumb" "-mfpu=fpv5-d16" "-mfloat-abi=hard")

# --- Console ---------------------------------------------------------------
# Pins are written as P<port><number>. CONSOLE_AF is the alternate function
# number; board.h turns it into GPIO_AF<n>_<uart>.
set(CONSOLE_UART "UART4")
set(CONSOLE_TX "PH13")
set(CONSOLE_RX "PH14")
set(CONSOLE_AF "8")
set(CONSOLE_BAUD "115200")

# --- Board clocks ----------------------------------------------------------
# Crystal fitted on the board, not a property of the chip, so the CMSIS-Pack
# does not know it. The HAL header defaults to 25 MHz, which is wrong here.
# Unused until you write SystemClock_Config; wrong values bite there.
set(HSE_HZ "8000000")

# --- RTOS ------------------------------------------------------------------
# "freertos" (the default) or "none" for a bare main loop. setup.py checks out
# the kernel; the build picks the port to use out of CPU_FLAGS on its own.
# Another RTOS is a cmake/rtos-<name>.cmake of its own, named here: CMakeLists
# includes whatever this says and nothing else looks at it.
set(RTOS "freertos")

# FreeRTOS heap (heap_4), in KB. Task stacks, queues and timers all come out of
# it, and it is one plain array in RAM, so it has to fit next to everything
# else there. The linker says "region RAM overflowed" when it does not.
set(FREERTOS_HEAP_KB "8")

# --- Extra libraries -------------------------------------------------------
# Added by `tools/setup.py add <alias|url>`. Each directory is scanned for
# *.c sources, and its Inc/ or Include/ subdirectory is added to the include
# path. Use this for BSP, example code, FreeRTOS, FatFS, etc.
set(EXTRA_LIB_DIRS "")
