# User-owned project configuration. Change targets with tools/setup.py target;
# that command updates BOARD/MCU and generated/device.cmake together.
# (python3 on macOS/Linux, python on Windows.)
#
# tools/setup.py both reads and rewrites this file, so keep it to plain
# single-line set() calls: one per line, no if()/foreach(), and no ')' inside
# a value. Trailing '#' comments are fine and are preserved on rewrite.
# setup.py target writes BOARD, MCU, target-specific console/clock choices and
# the explicit overrides below. Other commands may write ARM_TOOLCHAIN_BIN or
# EXTRA_LIB_DIRS. Physical device facts do not live in this file.

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
# Do not edit BOARD/MCU independently. Use one atomic command instead:
#   python3 tools/setup.py target --board NUCLEO-F411RE
#   python3 tools/setup.py target --mcu STM32F411RETx
set(BOARD "CoreH743I")
set(MCU "STM32H743IITx")

# --- Target policy and explicit overrides ----------------------------------
# RAM defaults to whatever the pack puts at 0x20000000, which is TCM or main
# SRAM on supported STM32s and works straight out of reset. Select another with
# `setup.py target ... --ram-region RAM_D1`; retargeting clears this value.
# On STM32H743 the choices are DTCMRAM (128K, the default), RAM_D1 (512K),
# RAM_D2 (288K) and RAM_D3 (64K). RAM_D2 and RAM_D3 need their RCC clocks
# enabled before first access, so do not point at them without adding that.
set(RAM_REGION "")

# Pack-derived values live in generated/device.cmake. Override one only when
# deliberately departing from the device pack. Every target change clears all
# overrides so a value for one MCU cannot silently leak into another.
set(TARGET_FLASH_ORIGIN_OVERRIDE "")
set(TARGET_FLASH_SIZE_OVERRIDE "")
set(TARGET_RAM_ORIGIN_OVERRIDE "")
set(TARGET_RAM_SIZE_OVERRIDE "")
set(TARGET_DEVICE_DEFINE_OVERRIDE "")
set(TARGET_CPU_FLAGS_OVERRIDE "")

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
