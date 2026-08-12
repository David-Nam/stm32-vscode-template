# Turns the values in config.cmake into sources, include paths and flags.
# Everything here is derived; nothing is per-family hardcoded.

foreach(var FAMILY DEVICE_DEFINE CPU_FLAGS FLASH_ORIGIN FLASH_SIZE RAM_ORIGIN RAM_SIZE)
  if(NOT ${var})
    message(FATAL_ERROR "${var} is empty in config.cmake. Run: python3 tools/setup.py")
  endif()
endforeach()

string(TOLOWER "${FAMILY}" FAM)
string(TOLOWER "${DEVICE_DEFINE}" DEVICE)   # STM32H743xx -> stm32h743xx

set(CMSIS_DEV ${CMAKE_SOURCE_DIR}/lib/cmsis-device-${FAM})
set(HAL       ${CMAKE_SOURCE_DIR}/lib/stm32${FAM}xx-hal-driver)

# cmsis-core has moved core_cmX.h between releases: CMSIS 6 puts it under
# CMSIS/Core/Include, older drops it straight in Include.
find_path(CMSIS_CORE_INC core_cm7.h core_cm4.h core_cm0plus.h core_cm33.h core_cm3.h
  PATHS ${CMAKE_SOURCE_DIR}/lib/cmsis-core/CMSIS/Core/Include
        ${CMAKE_SOURCE_DIR}/lib/cmsis-core/Include
  NO_DEFAULT_PATH)
if(NOT CMSIS_CORE_INC)
  message(FATAL_ERROR "no core_cmX.h under lib/cmsis-core. Run: python3 tools/setup.py")
endif()

# --- Startup and system code ------------------------------------------------
# Both file names follow from the device define, so no lookup table is needed.
set(STARTUP ${CMSIS_DEV}/Source/Templates/gcc/startup_${DEVICE}.s)
set(SYSTEM  ${CMSIS_DEV}/Source/Templates/system_stm32${FAM}xx.c)
foreach(f ${STARTUP} ${SYSTEM})
  if(NOT EXISTS ${f})
    message(FATAL_ERROR "missing ${f}\n  Is DEVICE_DEFINE=${DEVICE_DEFINE} right for this family?")
  endif()
endforeach()

# --- HAL and LL sources -----------------------------------------------------
# Compile both and let --gc-sections drop what the application does not call.
# A non-recursive glob keeps Src/Legacy out; *_template.c are ST's stubs, meant
# to be copied into a project rather than built.
file(GLOB HAL_SRC CONFIGURE_DEPENDS ${HAL}/Src/*.c)
list(FILTER HAL_SRC EXCLUDE REGEX "_template\\.c$")
if(NOT HAL_SRC)
  message(FATAL_ERROR "no HAL sources under ${HAL}/Src. Run: python3 tools/setup.py")
endif()

set(STM32_SOURCES ${STARTUP} ${SYSTEM} ${HAL_SRC})
set(STM32_INCLUDES
  ${CMSIS_CORE_INC}
  ${CMSIS_DEV}/Include
  ${HAL}/Inc
  ${CMAKE_SOURCE_DIR}/inc
  ${CMAKE_BINARY_DIR})

# Keeps the family out of application code: main.c includes "board.h".
# Split P<port><number> into the two halves the HAL macros need.
foreach(sig TX RX)
  if(NOT CONSOLE_${sig} MATCHES "^P([A-Z])([0-9]+)$")
    message(FATAL_ERROR
      "CONSOLE_${sig}=\"${CONSOLE_${sig}}\" in config.cmake should look like PH13.\n"
      "  Which UART reaches your USB-serial bridge is board wiring, so it cannot\n"
      "  be derived. To list the pins and AF numbers this MCU offers:\n"
      "    python3 tools/setup.py pins")
  endif()
  set(CONSOLE_${sig}_PORT ${CMAKE_MATCH_1})
  set(CONSOLE_${sig}_PIN ${CMAKE_MATCH_2})
endforeach()
configure_file(${CMAKE_SOURCE_DIR}/cmake/board.h.in ${CMAKE_BINARY_DIR}/board.h @ONLY)

# --- Extra libraries added by `setup.py add` --------------------------------
foreach(dir ${EXTRA_LIB_DIRS})
  set(abs ${CMAKE_SOURCE_DIR}/${dir})
  if(NOT EXISTS ${abs})
    message(FATAL_ERROR "EXTRA_LIB_DIRS names ${dir}, which does not exist")
  endif()
  file(GLOB_RECURSE extra_src CONFIGURE_DEPENDS ${abs}/*.c)
  list(APPEND STM32_SOURCES ${extra_src})
  foreach(sub Inc Include inc include)
    if(IS_DIRECTORY ${abs}/${sub})
      list(APPEND STM32_INCLUDES ${abs}/${sub})
    endif()
  endforeach()
  message(STATUS "extra lib: ${dir}")
endforeach()

# --- Linker script ----------------------------------------------------------
set(HEAP_SIZE  0x200  CACHE STRING "minimum heap reserved by the linker script")
set(STACK_SIZE 0x400  CACHE STRING "minimum stack reserved by the linker script")
set(LINKER_SCRIPT ${CMAKE_BINARY_DIR}/${DEVICE}_flash.ld)
configure_file(${CMAKE_SOURCE_DIR}/cmake/stm32_flash.ld.in ${LINKER_SCRIPT} @ONLY)

# --- Flags ------------------------------------------------------------------
set(STM32_DEFINES ${DEVICE_DEFINE} USE_HAL_DRIVER USE_FULL_LL_DRIVER)
if(HSE_HZ)
  # stm32*_hal_conf.h guards HSE_VALUE, so this overrides its 25 MHz default.
  list(APPEND STM32_DEFINES HSE_VALUE=${HSE_HZ}UL)
endif()
set(STM32_COMPILE_OPTIONS ${CPU_FLAGS} -ffunction-sections -fdata-sections)
set(STM32_LINK_OPTIONS
  ${CPU_FLAGS}
  -T${LINKER_SCRIPT}
  --specs=nano.specs --specs=nosys.specs
  -Wl,--gc-sections
  -Wl,-Map=${CMAKE_BINARY_DIR}/${PROJECT_NAME}.map,--cref
  -Wl,--print-memory-usage
  # .init_array is writable and lands in the same FLASH segment as .text, so
  # the segment comes out RWX. There is no MMU enforcing W^X here and nothing
  # loads these segment flags -- the .bin is written straight to flash.
  -Wl,--no-warn-rwx-segments)
