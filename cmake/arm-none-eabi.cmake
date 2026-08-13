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

# Every other tool is looked up next to the compiler instead of being glued
# together as a string: on Windows the files are arm-none-eabi-objcopy.exe, and
# find_program adds that suffix where a hand-built path would not.
find_program(ARM_GXX     arm-none-eabi-g++     HINTS ${ARM_BIN} NO_DEFAULT_PATH)
find_program(ARM_OBJCOPY arm-none-eabi-objcopy HINTS ${ARM_BIN} NO_DEFAULT_PATH REQUIRED)
find_program(ARM_SIZE    arm-none-eabi-size    HINTS ${ARM_BIN} NO_DEFAULT_PATH REQUIRED)

set(CMAKE_C_COMPILER   "${ARM_GCC}")
set(CMAKE_ASM_COMPILER "${ARM_GCC}")
if(ARM_GXX)
  set(CMAKE_CXX_COMPILER "${ARM_GXX}")
endif()
set(CMAKE_OBJCOPY "${ARM_OBJCOPY}" CACHE FILEPATH "")
set(CMAKE_SIZE    "${ARM_SIZE}"    CACHE FILEPATH "")

set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
