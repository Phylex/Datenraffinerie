cmake_minimum_required(VERSION 3.0)
project(datenraffinerie-tools)

set(CMAKE_PREFIX_PATH ${CMAKE_BINARY_DIR})
set(CMAKE_MODULE_PATH ${CMAKE_BINARY_DIR})

find_library (zmq NAMES zmq REQUIRED)
find_package (yaml-cpp REQUIRED)


add_executable(yaml-test
	yaml-tools.h
	yaml_test.cpp)

target_link_libraries(yaml-test yaml-cpp)
