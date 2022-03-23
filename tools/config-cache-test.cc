#include "yaml-tools.h"
#include <yaml-cpp/yaml.h>
#include <vector>
#include <tuple>
#include <ranges>
#include <string>
#include <iostream>
#include "hgcroc_caching.h"


int main() {
	YAML::Node config = YAML::LoadFile("../../tests/configuration/defaults/V3LDHexaboard-poweron-default.yaml");
	YAML::Node overlay = YAML::LoadFile("../../tests/configuration/defaults/initLDV3.yaml");
	YAML::Node channel_overlay = YAML::LoadFile("../../tests/configuration/defaults/channel_settings.yaml");
	update<int>(config, overlay);
	update<int>(config, channel_overlay);
	std::vector<std::string> columns = {"S", "Delay9", "range_inv", "Toa_vref", "HighRange", "LowRange"};
	
	// test the key generation functions
	CacheKey test_t1(0, 40, 0);
	CacheKey test_t2(0, 20, 1);
	HalfWiseCacheKey hwt1 = calc_half_wise_cache_key(test_t1);
	CacheKey ct1 = transform_event_row_to_cache_key(test_t2);
	std::cout << "Calculated key from event data: " << std::get<0>(ct1) << " " << std::get<1>(ct1) << " " << std::get<2>(ct1) << std::endl;
	std::cout << "Calculated half wise key from summary data " << std::get<0>(hwt1) << " " << std::get<1>(hwt1) << std::endl;

	// test the cache generation functions
	// chnnel wise cache generation
	std::vector<std::string> channel_columns = filter_channel_columns(columns);
	std::cout << "Channel wise columns found in the column selection:" << std::endl;
	for (auto &col: channel_columns) {
		std::cout << col << std::endl;
	}
	std::cout << std::endl;
	std::map<CacheKey, std::vector<int>> channel_config = generate_hgcroc_chan_config_cache<int>(config, channel_columns);
	unsigned int channel_types[] = {0, 1, 100};
	for (unsigned int i = 0; i < 3; i++) {
		for (auto &type: channel_types) {
			for (unsigned int j = 0; j < channel_type_to_channel_cout[type]; j++) {
				CacheKey curr_key(i, j, type);
				std::cout << "Configuration cache for key: ("
						  << std::get<0>(curr_key) << ", " << std::get<1>(curr_key) << ", " << std::get<2>(curr_key) << "):\t";
				std::cout << "[ ";
				for (size_t column_index = 0; column_index < channel_columns.size(); column_index ++) {
					std::cout << channel_columns[column_index] << ": " << channel_config[curr_key][column_index] << ", ";
				}
				std::cout << "]" << std::endl;
			}
		}
	}
	std::cout << std::endl;
	std::cout << std::endl;

	// half wise channel generation
	std::vector<ConfigKey> half_wise_columns = filter_half_wise_columns(columns);
	std::cout << "Half wise columns found in the column selection:" << std::endl;
	for (auto &col: half_wise_columns) {
		std::cout << std::get<0>(col) << ", " << std::get<1>(col) << std::endl;
	}
	std::cout << std::endl;
	std::map<HalfWiseCacheKey, std::vector<int>> half_wise_config_cache = generate_hgcroc_halfwise_config<int>(config, half_wise_columns);
	for (unsigned int i = 0; i < 3; i++) {
		for (auto &type: channel_types) {
			for (unsigned int j = 0; j < channel_type_to_channel_cout[type]; j++) {
				CacheKey curr_key(i, j, type);
				HalfWiseCacheKey curr_hw_key = calc_half_wise_cache_key(curr_key);
				std::cout << "HalfWise config cache for key: ("
						  << std::get<0>(curr_key) << ", " << std::get<1>(curr_key) << ", " << std::get<2>(curr_key) << "):\t";
				std::cout << "[ ";
				for (size_t column_index = 0; column_index < half_wise_columns.size(); column_index ++) {
					std::cout << std::get<1>(half_wise_columns[column_index]) << ": " << half_wise_config_cache[curr_hw_key][column_index] << ", ";
				}
				std::cout << "]" << std::endl;
			}
		}
	}
	std::cout << std::endl;
	std::cout << std::endl;
	

	// global channel config
	std::vector<ConfigKey> global_columns = filter_global_columns(columns);
	std::cout << "Global columns found in the column selection:" << std::endl;
	for (auto &col: global_columns) {
		std::cout << std::get<0>(col) << ", " << std::get<1>(col) << std::endl;
	}
	std::cout << std::endl;
	std::map<GlobalCacheKey, std::vector<int>> global_config_cache = generate_hgcroc_global_config<int>(config, half_wise_columns);
	for (unsigned int i = 0; i < 3; i++) {
		for (auto &type: channel_types) {
			for (unsigned int j = 0; j < channel_type_to_channel_cout[type]; j++) {
				CacheKey curr_key(i, j, type);
				GlobalCacheKey curr_global_key = calc_global_cache_key(curr_key);
				std::cout << "Global config cache for key: ("
						  << std::get<0>(curr_key) << ", " << std::get<1>(curr_key) << ", " << std::get<2>(curr_key) << "):\t";
				std::cout << "[ ";
				for (size_t column_index = 0; column_index < global_columns.size(); column_index ++) {
					std::cout << std::get<1>(global_columns[column_index]) << ": " << global_config_cache[curr_global_key][column_index] << ", ";
				}
				std::cout << "]" << std::endl;
			}
		}
	}
	std::cout << std::endl;
	std::cout << std::endl;
}
