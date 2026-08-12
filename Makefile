BUILD ?= build

.PHONY: all clean

all: $(BUILD)/Makefile
	@cmake --build $(BUILD)

$(BUILD)/Makefile:
	@cmake -S . -B $(BUILD) -G "Unix Makefiles" \
		-DCMAKE_TOOLCHAIN_FILE=cmake/arm-none-eabi.cmake \
		-DCMAKE_EXPORT_COMPILE_COMMANDS=ON

clean:
	@rm -rf $(BUILD)
