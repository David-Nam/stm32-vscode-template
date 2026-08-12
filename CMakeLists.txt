cmake_minimum_required(VERSION 3.20)

include(${CMAKE_CURRENT_LIST_DIR}/config.cmake)

project(stm32-template C ASM)

message(STATUS "MCU:       ${MCU} (${BOARD})")
message(STATUS "Toolchain: ${CMAKE_C_COMPILER}")

include(${CMAKE_CURRENT_LIST_DIR}/cmake/stm32.cmake)

file(GLOB APP_SOURCES CONFIGURE_DEPENDS src/*.c)

add_executable(${PROJECT_NAME}.elf ${APP_SOURCES} ${STM32_SOURCES})
target_include_directories(${PROJECT_NAME}.elf PRIVATE ${STM32_INCLUDES})
target_compile_definitions(${PROJECT_NAME}.elf PRIVATE ${STM32_DEFINES})
target_compile_options(${PROJECT_NAME}.elf PRIVATE ${STM32_COMPILE_OPTIONS})
target_link_options(${PROJECT_NAME}.elf PRIVATE ${STM32_LINK_OPTIONS})

# Warnings on our own code only. The vendor drivers are not ours to clean up.
set_source_files_properties(${APP_SOURCES} PROPERTIES COMPILE_OPTIONS "-Wall;-Wextra")

set(ELF $<TARGET_FILE:${PROJECT_NAME}.elf>)
add_custom_command(TARGET ${PROJECT_NAME}.elf POST_BUILD
  COMMAND ${CMAKE_OBJCOPY} -O ihex   ${ELF} ${PROJECT_NAME}.hex
  COMMAND ${CMAKE_OBJCOPY} -O binary ${ELF} ${PROJECT_NAME}.bin
  COMMAND ${CMAKE_SIZE} ${ELF})

# Writes to FLASH_ORIGIN, so an app placed behind a bootloader still lands right.
add_custom_target(flash
  COMMAND st-flash --reset write ${PROJECT_NAME}.bin ${FLASH_ORIGIN}
  DEPENDS ${PROJECT_NAME}.elf
  WORKING_DIRECTORY ${CMAKE_BINARY_DIR}
  COMMENT "st-flash write ${PROJECT_NAME}.bin ${FLASH_ORIGIN}")
