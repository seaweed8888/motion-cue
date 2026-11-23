cmake_minimum_required(VERSION 3.16)

# The chip is confirmed; GPIOs and sensor settings still depend on the board.
set(IDF_TARGET "esp32s3")
set(EXTRA_COMPONENT_DIRS "${CMAKE_CURRENT_LIST_DIR}/src")
set(COMPONENTS src)
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(motionlink)
