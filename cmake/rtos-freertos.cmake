# FreeRTOS kernel sources, port and generated FreeRTOSConfig.h.
# Included by CMakeLists.txt when RTOS is "freertos" in config.cmake, after
# stm32.cmake, so it only appends to the lists that one built.

set(FREERTOS ${CMAKE_SOURCE_DIR}/lib/freertos-kernel)
if(NOT EXISTS ${FREERTOS}/tasks.c)
  message(FATAL_ERROR "lib/freertos-kernel is empty. Run: ${PY} tools/setup.py")
endif()

# --- Port -------------------------------------------------------------------
# The port follows from the core, which is already in CPU_FLAGS, so there is
# nothing to configure. CMSIS_HANDLER_NAMES marks the newer ports: those define
# SVC_Handler, PendSV_Handler and SysTick_Handler themselves and ship a
# portasm.c, where the older ones use their own names and need the aliases in
# FreeRTOSConfig.h.in to reach the vector table.
if(NOT CPU_FLAGS MATCHES "-mcpu=([a-z0-9.+-]+)")
  message(FATAL_ERROR "CPU_FLAGS has no -mcpu=: ${CPU_FLAGS}")
endif()
set(CORE ${CMAKE_MATCH_1})

if(CORE STREQUAL "cortex-m0" OR CORE STREQUAL "cortex-m0plus")
  set(PORT ARM_CM0)
  set(CMSIS_HANDLER_NAMES TRUE)
elseif(CORE STREQUAL "cortex-m3")
  set(PORT ARM_CM3)
elseif(CORE STREQUAL "cortex-m4")
  # Without an FPU there is nothing extra to save on a switch, and that is the
  # only thing the M4F port adds over the M3 one.
  if(CPU_FLAGS MATCHES "float-abi=hard")
    set(PORT ARM_CM4F)
  else()
    set(PORT ARM_CM3)
  endif()
elseif(CORE STREQUAL "cortex-m7")
  set(PORT ARM_CM7/r0p1)
elseif(CORE STREQUAL "cortex-m23")
  set(PORT ARM_CM23_NTZ/non_secure)
  set(CMSIS_HANDLER_NAMES TRUE)
elseif(CORE STREQUAL "cortex-m33")
  set(PORT ARM_CM33_NTZ/non_secure)
  set(CMSIS_HANDLER_NAMES TRUE)
elseif(CORE STREQUAL "cortex-m55")
  set(PORT ARM_CM55_NTZ/non_secure)
  set(CMSIS_HANDLER_NAMES TRUE)
elseif(CORE STREQUAL "cortex-m85")
  set(PORT ARM_CM85_NTZ/non_secure)
  set(CMSIS_HANDLER_NAMES TRUE)
else()
  message(FATAL_ERROR
    "no FreeRTOS port mapped for ${CORE}.\n"
    "  Pick the matching directory from lib/freertos-kernel/portable/GCC and\n"
    "  add it to cmake/rtos-freertos.cmake.")
endif()

# NTZ is the non-TrustZone build of the ARMv8-M ports: one image, no secure
# side. A TrustZone project needs the plain ARM_CM33 port and a secure image
# to go with it, which is a project of its own, not a switch here.
set(PORT_DIR ${FREERTOS}/portable/GCC/${PORT})
message(STATUS "RTOS:      FreeRTOS, port ${PORT}")

# --- Sources ----------------------------------------------------------------
# The kernel is the *.c at the top of the repo; everything else is opt-in.
# heap_4 is the general-purpose allocator: it coalesces neighbouring free
# blocks, which the others do not. Swap the file to change that.
file(GLOB FREERTOS_SRC CONFIGURE_DEPENDS ${FREERTOS}/*.c)
list(APPEND FREERTOS_SRC ${PORT_DIR}/port.c ${FREERTOS}/portable/MemMang/heap_4.c)
if(CMSIS_HANDLER_NAMES)
  list(APPEND FREERTOS_SRC ${PORT_DIR}/portasm.c)
endif()

list(APPEND STM32_SOURCES ${FREERTOS_SRC})
list(APPEND STM32_INCLUDES ${FREERTOS}/include ${PORT_DIR})
list(APPEND STM32_DEFINES RTOS_FREERTOS)

# --- Config header ----------------------------------------------------------
if(CMSIS_HANDLER_NAMES)
  set(HANDLER_ALIASES "/* This port already defines the CMSIS handler names. */")
else()
  string(CONCAT HANDLER_ALIASES
      "#define vPortSVCHandler     SVC_Handler\n"
      "#define xPortPendSVHandler  PendSV_Handler\n"
      "#define xPortSysTickHandler SysTick_Handler")
endif()
configure_file(${CMAKE_SOURCE_DIR}/cmake/FreeRTOSConfig.h.in
               ${CMAKE_BINARY_DIR}/FreeRTOSConfig.h @ONLY)
