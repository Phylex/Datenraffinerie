#include "include/hgcroc_caching.h"

std::vector<ConfigKey> filter_global_columns (std::vector<std::string> columns) {
	std::vector<std::tuple<std::string, std::string>> filtered_global_cols;
	for (auto col: columns) {
		for (auto available_col: roc_global_config) {
			if (std::get<1>(available_col) == col) {
				filtered_global_cols.push_back(available_col);
			}
		}
	}
	return filtered_global_cols;
}

std::vector<ConfigKey> filter_half_wise_columns (std::vector<std::string> columns) {
	std::vector<ConfigKey> filtered_half_wise_cols;
	for (auto col: columns) {
		for (auto available_col: roc_half_config) {
			if (std::get<1>(available_col) == col) {
				filtered_half_wise_cols.push_back(available_col);
				break;
			}
		}
	}
	return filtered_half_wise_cols;
}

std::vector<std::string> filter_channel_columns(std::vector<std::string> columns) {
	std::vector<std::string> channel_cols;
	for (auto col: columns) {
		for (auto available_col: chan_config_params) {
			if (col == available_col) {
				channel_cols.push_back(col);
				break;
			}
		}
	}
	return channel_cols;
}

GlobalCacheKey calc_global_cache_key(CacheKey row_key) {
	return std::get<0>(row_key);
};

HalfWiseCacheKey calc_half_wise_cache_key(CacheKey row_key) {
	unsigned int chip = std::get<0>(row_key);
	unsigned int channel = std::get<1>(row_key);
	unsigned int type = std::get<2>(row_key);
	unsigned int half = 0;
	if (type == 0) {
		if (channel < 36) {
			half = 0;
		} else {
			half = 1;
		}
	} else if (type == 1) {
		half = channel;
	} else if (type == 100) {
		if (channel < 3) {
			half = 0;
		} else {
			half = 1;
		}
	}
	HalfWiseCacheKey key = {chip, half};
	return key;
}


CacheKey transform_event_row_to_cache_key(CacheKey row_key) {
	unsigned int chip = std::get<0>(row_key);
	unsigned int channel = std::get<1>(row_key);
	unsigned int half = std::get<2>(row_key);
	unsigned int out_channel;
	unsigned int out_type;
	if (channel <= 35) {
		out_channel = channel * (half + 1);
		out_type = 0;
	} else if (channel == 36) {
		out_channel = half;
		out_type = 1;
	} else {
		out_channel = channel - 37 + ( half * 2);
		out_type = 100;
	}
	CacheKey out_key(chip, out_channel, out_type);
	return out_key;
}
