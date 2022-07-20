#include "daq_system_parameters.h"
#include <map>

std::string keyarr[] = {"enable", "BX", "length", "flavour", "prescale", "followMode"};

std::map<std::string, int> get_l1a_generator_settings(YAML::Node system_config) {
  std::map<std::string, int> val_map = std::map<std::string, int>();
  YAML::Node server_l1a_generator_config = system_config["daq"]["server"]["l1a_generator_settings"];
  for (size_t i = 0; i < server_l1a_generator_config.size(); i++) {
    std::string name = server_l1a_generator_config[i]["name"].as<std::string>();
    std::stringstream key;
    for (std::string suffix: keyarr) {
      key << name << "_" << suffix;
      int value = server_l1a_generator_config[suffix].as<int>();
      val_map.insert( std::pair<std::string, int>(key.str(), value));
      key.str("");
    } 
  }
  return val_map;
}

