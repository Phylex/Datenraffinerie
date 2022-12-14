cmake_minimum_required(VERSION 3.0)
project(datenraffinerie-tools LANGUAGES CXX C)

include_directories(include)

set(CMAKE_CXX_STANDARD 11)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(CMAKE_PREFIX_PATH ${CMAKE_BINARY_DIR})
set(CMAKE_MODULE_PATH ${CMAKE_BINARY_DIR})

find_library (zmq NAMES zmq REQUIRED)
find_package (yaml-cpp REQUIRED)
find_package (HDF5 REQUIRED COMPONENTS CXX C HL)
find_package (ROOT REQUIRED)

# generate the roc_param_description.hpp file
add_custom_command(
	OUTPUT roc_param_description.hpp
	COMMAND python3 ${CMAKE_CURRENT_SOURCE_DIR}/utilities/generate_roc_structs.py ${CMAKE_CURRENT_SOURCE_DIR}/utilities/HGCROC3_I2C_params_regmap.csv ${CMAKE_CURRENT_SOURCE_DIR}/utilities/code_struct_template.cpp ${CMAKE_CURRENT_BINARY_DIR}/roc_param_description.hpp
	COMMENT "Generating roc parameter structs"
)

# compile the main libraries
add_library(
	hgcroc-caching
	hgcroc_caching.cc
	${CMAKE_CURRENT_BINARY_DIR}/roc_param_description.hpp)

add_library(hdf-utils hdf-utils.cc ${CMAKE_CURRENT_BINARY_DIR}/roc_param_description.hpp)
target_link_libraries(hdf-utils
  PUBLIC HDF5::HDF5 
  root-tools
)

add_library(root-tools
	root-tools.cc )
target_link_libraries(root-tools
	PUBLIC ROOT::Core
	ROOT::Tree 
	ROOT::RIO)

# compile the main thest executables
add_executable(hdf-test
	test-hdf-utils.cc)
target_link_libraries(hdf-test
	HDF5::HDF5
	hdf-utils
	ROOT::Core
	ROOT::Tree)

add_executable(config-cache-test
	config-cache-test.cc )
target_link_libraries(config-cache-test
	yaml-cpp
	hgcroc-caching
	HDF5::HDF5)

# compile the applications used to get familiar with the
# libraries used
add_executable(yaml-test
	yaml_test.cpp)
target_link_libraries(yaml-test yaml-cpp)

add_executable(hdf-hyperslab
	hdf5-hyperslab-experiments.cc )
target_link_libraries(hdf-hyperslab
	HDF5::HDF5)

add_executable(hdf-extended-dataset
	hdf5-extended-dataset-experiments.cc )
target_link_libraries(hdf-extended-dataset
	HDF5::HDF5)

add_executable(test_datastruct
	test_roc_datastructures.cpp )
target_link_libraries(test_datastruct
	HDF5::HDF5)

add_executable( fracker
	fracker.cc )
target_link_libraries(fracker
	hdf-utils
	hgcroc-caching
	yaml-cpp
	root-tools
	ROOT::Core )
install( TARGETS fracker
	CONFIGURATIONS Release
	RUNTIME DESTINATION bin )

add_executable( turbo-pump
	turbo-pump.cc )
target_link_libraries( turbo-pump
	hdf-utils )
install( TARGETS turbo-pump
	CONFIGURATIONS Release
	RUNTIME DESTINATION bin )
