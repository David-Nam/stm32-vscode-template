BUILD ?= build

.PHONY: all clean flash

all: $(BUILD)/Makefile
	@cmake --build $(BUILD)

flash: all
	@cmake --build $(BUILD) --target flash

$(BUILD)/Makefile:
	@cmake -S . -B $(BUILD) -G "Unix Makefiles" \
		-DCMAKE_TOOLCHAIN_FILE=cmake/arm-none-eabi.cmake \
		-DCMAKE_EXPORT_COMPILE_COMMANDS=ON

clean:
	@rm -rf $(BUILD)
