# Project configuration. This is the only file you should need to edit.
# After changing MCU or BOARD, run: python3 tools/setup.py
#
# tools/setup.py both reads and rewrites this file, so keep it to plain
# single-line set() calls: one per line, no if()/foreach(), and no ')' inside
# a value. Trailing '#' comments are fine and are preserved on rewrite.
# setup.py only ever writes MCU, CONSOLE_*, RAM_*, FLASH_SIZE (and only when
# they are empty) plus EXTRA_LIB_DIRS. Everything else it just reads.

# --- Toolchain -------------------------------------------------------------
# Leave empty to use whatever arm-none-eabi-gcc is on PATH.
# Note: Homebrew's arm-none-eabi-gcc ships without newlib, so printf will not
# link against it. Use an Arm GNU Toolchain release instead.
set(ARM_TOOLCHAIN_BIN "$ENV{HOME}/.local/opt/arm-gnu-toolchain-15.3.rel1-darwin-arm64-arm-none-eabi/bin")

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
set(CONSOLE_UART "USART1")
set(CONSOLE_TX "PA9")
set(CONSOLE_RX "PA10")
set(CONSOLE_AF "7")
set(CONSOLE_BAUD "115200")

# --- Extra libraries -------------------------------------------------------
# Added by `tools/setup.py add <alias|url>`. Each directory is scanned for
# *.c sources, and its Inc/ or Include/ subdirectory is added to the include
# path. Use this for BSP, example code, FreeRTOS, FatFS, etc.
set(EXTRA_LIB_DIRS "")
