#ifndef _HGCROC_CACHING_H_
#define _HGCROC_CACHING_H_
#include <yaml-cpp/yaml.h>
#include <map>
#include <iostream>
#include <tuple>
#include <vector>
#include <array>
#include <algorithm>
#include <hdf5.h>
#include "roc_param_description.hpp"

#define ROC_CHAN_TYPE 0
#define ROC_CALIB_CHAN_TYPE 1
#define ROC_CM_CHAN_TYPE 100

static std::array<unsigned int, 3> channel_types = {
	ROC_CHAN_TYPE,
	ROC_CALIB_CHAN_TYPE,
	ROC_CM_CHAN_TYPE
};

static std::map<unsigned int, int> channel_count = {
	{ROC_CHAN_TYPE, 72},
	{ROC_CALIB_CHAN_TYPE, 4},
	{ROC_CM_CHAN_TYPE, 2}
};

static std::map<unsigned int, std::string> channel_type_index_to_name = {
	{ROC_CHAN_TYPE, "ch"},
	{ROC_CALIB_CHAN_TYPE, "calib"},
	{ROC_CM_CHAN_TYPE, "cm"}
};

static std::map<std::string, unsigned int> channel_type_name_to_index = {
	{"ch", ROC_CHAN_TYPE},
	{"calib", ROC_CALIB_CHAN_TYPE},
	{"cm", ROC_CM_CHAN_TYPE}
};

static std::map<unsigned int, std::string> chip_num_to_name = {
	{0, "roc_s0"},
	{1, "roc_s1"},
	{2, "roc_s2"},
	{3, "roc_s3"},
	{4, "roc_s4"},
	{5, "roc_s5"}
};

using CacheKey = std::tuple<unsigned int, unsigned int, unsigned int>;

std::vector<CacheKey> generate_cache_key(int roc, std::string block_name, int block_number);
CacheKey transform_event_row_to_cache_key(CacheKey row_key);

template<typename T>
std::map<CacheKey, std::vector<T>> generate_hgcroc_config_cache(YAML::Node config, std::vector<std::string> columns){
	// allocate the result variables
	std::map<CacheKey, std::vector<T>> cache;
	std::vector<std::string> filtered_columns;

	// filter columns that actually belong to the configuration
	for (auto column: columns) {
		if (roc_config_key.find(column) != roc_config_key.end()) {
			filtered_columns.push_back(column);
		}
	}

	YAML::Node roc_config;
	// find the part of the config containing the roc config
	if (config["target"]) {
		roc_config = config["target"];
	} else {
		roc_config = config;
	}

	for (std::string column: filtered_columns) {
		for(auto yaml_key: roc_config_key[column]) {
			for (int i=0; i<roc_config.size(); i++) {
				std::vector<CacheKey> cache_keys = generate_cache_key(i, std::get<0>(yaml_key), std::get<1>(yaml_key));
				for (auto key: cache_keys) {
					std::vector<T> entry;
					if(cache.find(key) != cache.end()) {
						entry = cache[key];
					} else {
						entry.clear();
					}
					entry.push_back(config[chip_num_to_name[std::get<0>(key)]][std::get<0>(yaml_key)][std::get<1>(yaml_key)][std::get<2>(yaml_key)].as<T>());
					cache[key] = entry;
				}
			}
		}
	}
	return cache;
}
#endif
