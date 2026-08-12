# Project configuration. This is the only file you should need to edit.

# --- Toolchain -------------------------------------------------------------
# Leave empty to use whatever arm-none-eabi-gcc is on PATH.
# Note: Homebrew's arm-none-eabi-gcc ships without newlib, so printf will not
# link against it. Use an Arm GNU Toolchain release instead.
set(ARM_TOOLCHAIN_BIN "$ENV{HOME}/.local/opt/arm-gnu-toolchain-15.3.rel1-darwin-arm64-arm-none-eabi/bin")

# --- Target ----------------------------------------------------------------
# Reference board: Waveshare CoreH743I (HSE 8 MHz, LSE 32.768 kHz, 8 MB SDRAM)
set(MCU   "STM32H743IITx")
set(BOARD "CoreH743I")

# Stage 3 derives these from MCU. Hardcoded for now so stage 1 can compile.
set(CPU_FLAGS -mcpu=cortex-m7 -mthumb -mfpu=fpv5-d16 -mfloat-abi=hard)
