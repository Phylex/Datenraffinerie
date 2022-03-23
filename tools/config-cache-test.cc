#include "yaml-tools.h"
#include <yaml-cpp/yaml.h>
#include <vector>
#include <string>
#include <iostream>
#include "hgcroc_caching.h"

int main() {
	YAML::Node config = YAML::LoadFile("../../tests/configuration/defaults/V3LDHexaboard-poweron-default.yaml");
	YAML::Node overlay = YAML::LoadFile("../../tests/configuration/defaults/initLDV3.yaml");
	config = update<int>(config, overlay);
	std::vector<std::string> columns = {"S", "Toa_vref", "HighRange", "LowRange"};
	CacheKey test_t1(0, 40, 0);
	CacheKey test_t2(0, 20, 1);
	HalfWiseCacheKey hwt1 = calc_half_wise_key_summary_data(test_t1);
	CacheKey ct1 = calc_channel_cache_key_event_data(test_t2);
	std::cout << "Calculated key from event data: " << std::get<0>(ct1) << " " << std::get<1>(ct1) << " " << std::get<2>(ct1) << std::endl;
	std::cout << "Calculated half wise key from summary data " << std::get<0>(hwt1) << " " << std::get<1>(hwt1) << std::endl;
}
