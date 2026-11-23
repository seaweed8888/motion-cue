# Optional GNU Make shortcuts. Run from an activated EIM / ESP-IDF terminal.
PYTHON ?= python
IDF_PY ?= $(PYTHON) "$(IDF_PATH)/tools/idf.py"
BUILD_DIR ?= build
PORT ?=
BAUD ?= 460800

.DEFAULT_GOAL := build
.PHONY: help build flash monitor flash-monitor menuconfig size clean

help:
	@echo "Run from EIM: Manage Installations > Open Dashboard > Open IDF Terminal"
	@echo "make build                       Build ESP32-S3 firmware"
	@echo "make flash PORT=COM5             Build and flash firmware"
	@echo "make monitor PORT=COM5           Open serial monitor"
	@echo "make flash-monitor PORT=COM5     Build, flash, and monitor"
	@echo "make menuconfig                  Configure board-specific settings"
	@echo "make size                        Report firmware size"
	@echo "make clean                       Clean build output"

build menuconfig size clean:
	$(IDF_PY) -B "$(BUILD_DIR)" $@

flash monitor flash-monitor:
	$(if $(strip $(PORT)),,$(error Set PORT to your board's serial port, for example PORT=COM5))
	$(IDF_PY) -B "$(BUILD_DIR)" -p "$(PORT)" -b $(BAUD) $(if $(filter flash-monitor,$@),flash monitor,$@)
