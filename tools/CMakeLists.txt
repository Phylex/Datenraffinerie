cmake_minimum_required(VERSION 3.0)
project(datenraffinerie-tools)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_EXPORT_COMPILE_COMMANDS=ON)
set(CMAKE_PREFIX_PATH ${CMAKE_BINARY_DIR})
set(CMAKE_MODULE_PATH ${CMAKE_BINARY_DIR})

find_library (zmq NAMES zmq REQUIRED)
find_package (yaml-cpp REQUIRED)


add_executable(yaml-test
	yaml-tools.h
	yaml_test.cpp)

add_executable(config-cache-test
	config-cache-test.cc
	yaml-tools.h
	hgcroc_caching.h)

add_library(hgcroc-caching
	hgcroc_caching.cc
	hgcroc_caching.h)

target_link_libraries(yaml-test yaml-cpp)
target_link_libraries(config-cache-test
	yaml-cpp
	hgcroc-caching)
