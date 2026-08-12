cmake_minimum_required(VERSION 3.20)

include(${CMAKE_CURRENT_LIST_DIR}/config.cmake)

project(stm32-template C ASM)

message(STATUS "MCU:       ${MCU} (${BOARD})")
message(STATUS "Toolchain: ${CMAKE_C_COMPILER}")

# Stage 1: compile only. Linking needs startup code and a linker script from
# the CMSIS submodule, which stage 2 fetches and stage 3 wires up.
add_library(app OBJECT src/main.c)
target_compile_options(app PRIVATE ${CPU_FLAGS} -Wall -Wextra)
