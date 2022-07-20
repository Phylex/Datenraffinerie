#ifndef _DAQ_SYSTEM_PARAMS_
#define _DAQ_SYSTEM_PARAMS_
#include <hdf5.h>
#include <string>
#include <vector>
#include <tuple>
#include <map>
#include <yaml-cpp/yaml.h>

static std::map<std::string, hid_t> daq_column_type {
  {"A_enable", H5T_STD_I16LE},
  {"B_enable", H5T_STD_I16LE},
  {"C_enable", H5T_STD_I16LE},
  {"D_enable", H5T_STD_I16LE},
  {"A_BX", H5T_STD_I16LE},
  {"B_BX", H5T_STD_I16LE},
  {"C_BX", H5T_STD_I16LE},
  {"D_BX", H5T_STD_I16LE},
  {"A_length", H5T_STD_I16LE},
  {"B_length", H5T_STD_I16LE},
  {"C_length", H5T_STD_I16LE},
  {"D_length", H5T_STD_I16LE},
  {"A_prescale", H5T_STD_I16LE},
  {"B_prescale", H5T_STD_I16LE},
  {"C_prescale", H5T_STD_I16LE},
  {"D_prescale", H5T_STD_I16LE},
};

std::map<std::string, int> get_l1a_generator_settings(YAML::Node);
#endif

