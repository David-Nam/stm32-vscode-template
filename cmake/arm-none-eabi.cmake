# CMake toolchain file for bare-metal ARM.

set(CMAKE_SYSTEM_NAME Generic)
set(CMAKE_SYSTEM_PROCESSOR arm)

# CMake's compiler probe links a test program. There is no linker script or
# startup code at probe time, so build a static library instead.
set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)

include("${CMAKE_CURRENT_LIST_DIR}/../config.cmake" OPTIONAL)

find_program(ARM_GCC arm-none-eabi-gcc
  HINTS ${ARM_TOOLCHAIN_BIN} $ENV{ARM_TOOLCHAIN_BIN}
  REQUIRED)
get_filename_component(ARM_BIN "${ARM_GCC}" DIRECTORY)

set(CMAKE_C_COMPILER   "${ARM_BIN}/arm-none-eabi-gcc")
set(CMAKE_CXX_COMPILER "${ARM_BIN}/arm-none-eabi-g++")
set(CMAKE_ASM_COMPILER "${ARM_BIN}/arm-none-eabi-gcc")
set(CMAKE_OBJCOPY      "${ARM_BIN}/arm-none-eabi-objcopy" CACHE FILEPATH "")
set(CMAKE_SIZE         "${ARM_BIN}/arm-none-eabi-size"    CACHE FILEPATH "")

set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
