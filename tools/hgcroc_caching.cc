#include "include/hgcroc_caching.h"

bool validate_key(CacheKey key) {
	if (std::get<0>(key) > 6 || std::get<0>(key) < 0) return false;
	if (std::get<1>(key) > 71 || std::get<1>(key) < 0) return false;
	if (std::get<2>(key) != 1 && std::get<2>(key) != 0 && std::get<2>(key) != 100) return false;
	return true;
}


void transform_event_row_to_cache_key(CacheKey &row_key) {
	unsigned int chip = std::get<0>(row_key);
	unsigned int channel = std::get<1>(row_key);
	unsigned int half = std::get<2>(row_key);
	unsigned int out_channel;
	unsigned int out_type;
	if (channel <= 35) {
		out_channel = channel + (half * 36);
		out_type = 0;
	} else if (channel == 36) {
		out_channel = half;
		out_type = 1;
	} else {
		out_channel = channel - 37 + ( half * 2);
		out_type = 100;
	}
	std::get<1>(row_key) = out_channel;
	std::get<2>(row_key) = out_type;
}

std::vector<CacheKey> generate_cache_key(int roc, std::string block_name, int block_number) {
	std::vector<CacheKey> cache_keys;
	if (std::find(std::begin(global), std::end(global), block_name) != std::end(global)) {
		for (auto chan_type: channel_types) {
			for (int i=0; i<channel_count[chan_type]; i++) {
				CacheKey key(roc, i, chan_type);
				cache_keys.push_back(key);
			}
		}
	} else if (std::find(std::begin(half_wise), std::end(half_wise), block_name) != std::end(half_wise)) {
		for (auto chan_type: channel_types) {
			if (block_number == 0) {
				for (int i=0; i<channel_count[chan_type]/2; i++){
					CacheKey key(roc, i, chan_type);
					cache_keys.push_back(key);
				}
			} else if (block_number == 1){
				for (int i=channel_count[chan_type]/2; i<channel_count[chan_type]; i++) {
					CacheKey key(roc, i, chan_type);
					cache_keys.push_back(key);
				}
			}
		}
	} else if (std::find(std::begin(channel), std::end(channel), block_name) != std::end(channel)) {
		CacheKey key(roc, block_number, channel_type_name_to_index[block_name]);
		cache_keys.push_back(key);
	}
	return cache_keys;
}
