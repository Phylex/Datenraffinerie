#include "include/yaml-tools.h"
#include <yaml-cpp/yaml.h>
#include <vector>
#include <tuple>
#include <string>
#include <iostream>
#include "include/hgcroc_caching.h"


int main() {
	YAML::Node config = YAML::LoadFile("../../tests/configuration/defaults/V3LDHexaboard-poweron-default.yaml");
	if(config["target"])
		config = config["target"];
	YAML::Node overlay = YAML::LoadFile("../../tests/configuration/defaults/initLDV3.yaml");
	YAML::Node channel_overlay = YAML::LoadFile("../../tests/configuration/defaults/channel_settings.yaml");
	update<int>(config, overlay);
	update<int>(config, channel_overlay);
	std::vector<std::string> columns = {"S", "Delay9", "range_inv", "Toa_vref", "HighRange", "LowRange"};
	
	// test the key generation functions
	CacheKey test_t1(0, 40, 0);
	CacheKey test_t2(0, 20, 1);
	CacheKey ct1 = transform_event_row_to_cache_key(test_t2);
	std::cout << "Calculated key from event data: " << std::get<0>(ct1) << " " << std::get<1>(ct1) << " " << std::get<2>(ct1) << std::endl;

	// test the cache generation functions
	std::vector<std::string> config_columns;
	for (auto column: columns) {
		if (column_type.find(column) != column_type.end()) {
			config_columns.push_back(column);
		}
	}
	std::cout << "Channel wise columns found in the column selection:" << std::endl;
	for (auto &col: config_columns) {
		std::cout << col << std::endl;
	}
	std::cout << std::endl;

	std::map<CacheKey, std::vector<long>> cache = generate_hgcroc_config_cache<long>(config, columns);
	unsigned int channel_types[] = {0, 1, 100};
	for (unsigned int i = 0; i < 3; i++) {
		for (auto &type: channel_types) {
			for (unsigned int j = 0; j < channel_count[type]; j++) {
				CacheKey curr_key(i, j, type);
				std::cout << "Configuration cache for key: ("
						  << std::get<0>(curr_key) << ", " << std::get<1>(curr_key) << ", " << std::get<2>(curr_key) << "):\t";
				std::cout << "[ ";
				for (size_t column_index = 0; column_index < config_columns.size(); column_index ++) {
					std::cout << config_columns[column_index] << ": " << cache[curr_key][column_index] << ", ";
				}
				std::cout << "]" << std::endl;
			}
		}
	}
	for (size_t i = 0; i < 10000000; i++) {
		int channel = i % 72;
		CacheKey key(1, i, 0);
		std::vector<long> cache_row = cache[key];
	}
}
