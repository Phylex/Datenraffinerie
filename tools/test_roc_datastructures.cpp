#include "build/roc_param_description.hpp"
#include <iostream>

int main() {
  for (auto entry: roc_config_key) {
    for (auto instance: entry.second)
      std::cout << entry.first << std::get<0>(instance) << std::get<1>(instance) << std::get<2>(instance) << std::endl;
  }
}
