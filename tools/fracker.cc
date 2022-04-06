#include "include/CLI11.hpp"
#include "include/yaml-tools.h"
#include "include/hgcroc_caching.h"
#include "include/root-tools.h"
#include "include/hdf-utils.h"
#include <iostream>
#include <tuple>
#include <string>
#include <stdlib.h>
#include <TFile.h>
#include <TTree.h>

int main(int argc, char **argv) {
	CLI::App app{"Add the configuration information to the acquired data"};
	std::string default_config_path;
	std::string config_file_path;
	std::string data_file_path;
	std::string output_path;
	std::vector<std::string> columns;
	unsigned int block_size;

	/* set up the options of the command */
	app.add_option("-d", default_config_path, "default config of the target")
		->default_val("null");
	app.add_option("-c", config_file_path, "Run configuration file")
		->required()
		->check(CLI::ExistingFile);
	app.add_option("-i", data_file_path, "root file containing the data")
		->required()
		->check(CLI::ExistingFile);
	app.add_option("-b", block_size, "The size of a block to copy data from the root to the hdf file")
		->default_val(1000000);
	app.add_option("-s", columns, "The selection of columns that should appear in the output data");
	app.add_option("-o", output_path, "path to the output containing the data and config specified");

	/* parse the options */
	try {
		CLI11_PARSE(app, argc, argv);
	} catch (CLI::ValidationError e) {
		std::cout << "Invalid arguments " << e.what() << std::endl;
		exit(EXIT_FAILURE);
	}

	/* open the (overlay) config */
	YAML::Node config;	// this is the config that will hold the final config
	YAML::Node overlay_config;
	try {
		overlay_config = YAML::LoadFile(config_file_path);
		overlay_config = overlay_config["target"];
	} catch (YAML::BadFile e) {
		std::cout << "Unable to read YAML file " << config_file_path << std::endl;
		exit(EXIT_FAILURE);
	}

	/* if there is a default config load it and overlay it with the config */
	if ( default_config_path != "null") {
		YAML::Node default_config;
		try {
			default_config = YAML::LoadFile(default_config_path);
		} catch (YAML::BadFile e) {
			std::cout << "Unable to read YAML file " << default_config_path << std::endl;
			exit(EXIT_FAILURE);
		}
		update<int>(default_config, overlay_config);
		config = default_config;
	} else {
		config = overlay_config;
	}

	/* get the tree from the root file containing the data */
	bool event_mode;
	TFile *Measurement;
	TTree *measurement_tree = openRootTree(Measurement, data_file_path, &event_mode);
	std::vector<std::string> data_columns = filter_measurement_columns(event_mode, columns);

	/* create the output file and set it up */
	hid_t output = H5Fcreate(output_path.c_str(), H5F_ACC_TRUNC, H5P_DEFAULT, H5P_DEFAULT);
	hid_t group_id = set_up_file(output, "data");
	hid_t axis0 = 0;
	hid_t axis1 = 0;

	create_axes(group_id, &axis0, &axis1);

	/* generate the columns that are going to be used to store the data in */
	hid_t measurement_block = 0;
	if ( data_columns.size() > 0 ) {
		measurement_block = add_block(group_id, H5T_NATIVE_FLOAT, axis0, data_columns);
	} else {
		std::cout << "At least one Column of the measurement Data needs to be selected" << std::endl;
		exit(EXIT_FAILURE);
	}

	/* generate the cache of the configuration along with the blocks in the hdf file*/
	bool channel_cache = false;			// flag to tell the code if there is a channel wise cache
	bool half_wise_cache = false;		// flag to tell if there is a half wise cache
	bool global_cache = false;			// flag to say if there is a global cache
	bool config_columns = false;		// flag to say if there is any caching at all (OR of all previous flags)
	hid_t channel_config_block = 0;
	hid_t half_wise_config_block = 0;
	hid_t global_config_block = 0;
	/* generate channel wise config cache */
	std::vector<std::string> channel_columns = filter_channel_columns(columns);
	for (auto &col: channel_columns) {
	}
	std::map<CacheKey, std::vector<int>> channel_config;
	if (channel_columns.size() > 0 ) {
		try {
			channel_config = generate_hgcroc_chan_config_cache<int>(config, channel_columns);
		} catch (YAML::TypedBadConversion<int>) {
			std::cout << "Encountered an Error building the Channel Cache" << std::endl;
			std::cout << "Columns exported: " << std::endl;
			for (auto col: channel_columns) { 
				std::cout << col << ", ";
			}
			std::cout << std::endl;
			std::cout << "Config: " << std::endl << config <<std::endl;
			exit(EXIT_FAILURE);
		}
		channel_cache = true;
		channel_config_block = add_block(group_id, H5T_STD_I32LE, axis0, channel_columns);
	}
	/* generate the half wise configuration cache */
	std::vector<ConfigKey> half_wise_columns = filter_half_wise_columns(columns);
	std::map<HalfWiseCacheKey, std::vector<int>> half_wise_config;
	if (half_wise_columns.size() > 0 ) {
		std::vector<std::string> half_wise_column_names;
		for (ConfigKey ck: half_wise_columns) {
			half_wise_column_names.push_back(std::get<1>(ck));
		}
		try {
			half_wise_config = generate_hgcroc_halfwise_config<int>(config, half_wise_columns);
		} catch (YAML::TypedBadConversion<int>) {
			std::cout << "Encountered an Error building the Channel Cache" << std::endl;
			std::cout << "Columns exported: " << std::endl;
			for (auto col: channel_columns) { 
				std::cout << col << ", ";
			}
			std::cout << std::endl;
			std::cout << "Config: " << std::endl << config <<std::endl;
			exit(EXIT_FAILURE);
		}
		half_wise_cache = true;
		half_wise_config_block = add_block(group_id, H5T_STD_I32LE, axis0, half_wise_column_names);
	}
	/* generate the global config cache */
	std::vector<ConfigKey> global_columns = filter_global_columns(columns);
	std::map<GlobalCacheKey, std::vector<int>> global_config;
	if (global_columns.size() > 0 ) {
		std::vector<std::string> global_column_names;
		for (ConfigKey ck: global_columns) {
			global_column_names.push_back(std::get<1>(ck));
		}
		try {
			global_config = generate_hgcroc_global_config<int>(config, global_columns);
		} catch (YAML::TypedBadConversion<int>) {
			std::cout << "Encountered an Error building the Channel Cache" << std::endl;
			std::cout << "Columns exported: " << std::endl;
			for (auto col: channel_columns) { 
				std::cout << col << ", ";
			}
			std::cout << std::endl;
			std::cout << "Config: " << std::endl << config <<std::endl;
			exit(EXIT_FAILURE);
		}
		global_cache = true;
		global_config_block = add_block(group_id, H5T_STD_I32LE, axis0, global_column_names);
	}

	/* set up the arrays to buffer the data between the root and hdf files */
	float *m_data = (float *)malloc(data_columns.size() * sizeof(float));
	for (size_t i = 0; i < data_columns.size(); i++) {
		m_data[i] = 0;
	}
	float *m_block_buffer= (float *)malloc(block_size * data_columns.size() * sizeof(float));
	for (size_t i = 0; i < block_size *data_columns.size(); i++) {
		m_block_buffer[i] = 0;
	}

	/* set up the  values holding the cache key info */
	unsigned int chip;
	unsigned short channel;
	unsigned short channeltype;
	int e_chip;
	int half;
	int e_channel;

	/* if there is any channel_config info set up it's buffer and block storage */
	unsigned int* c_data_buffer = NULL;
	unsigned int* c_config_data = NULL;
	if ( channel_cache ) {
		c_config_data = (unsigned int *)malloc(block_size * channel_columns.size() * sizeof(unsigned int));
		for ( size_t i = 0; i < block_size * channel_columns.size(); i++ ) {
			c_config_data[i] = 0;
		}
	}
	/* do the same for the half wise config */
	unsigned int* hw_config_data = NULL;
	if ( half_wise_cache ) {
		hw_config_data = (unsigned int *)malloc(block_size * half_wise_columns.size() * sizeof(unsigned int));
		for ( size_t i = 0; i < block_size * half_wise_columns.size(); i++ ) {
			hw_config_data[i] = 0;
		}
	}
	/* and the global config */
	unsigned int* g_config_data = NULL;
	if ( global_cache ) {
		g_config_data = (unsigned int *)malloc(block_size * global_columns.size() * sizeof(unsigned int));
		for ( size_t i = 0; i < block_size * global_columns.size(); i++ ) {
			g_config_data[i] = 0;
		}
	}

	/* get the size of the data in the root file */
	size_t total_rows = measurement_tree->GetEntries();
	size_t blocks = total_rows / block_size + 1;
	

	/* link the entries of the keys to the variables to build the caching key */
	if ( event_mode ) {
		measurement_tree->SetBranchAddress("chip", &e_chip);
		measurement_tree->SetBranchAddress("half", &half);
		measurement_tree->SetBranchAddress("channel", &e_channel);
	} else {
		measurement_tree->SetBranchAddress("chip", &chip);
		measurement_tree->SetBranchAddress("channeltype", &channeltype);
		measurement_tree->SetBranchAddress("channel", &channel);
	}

	/* run through the root file, retrieve the config from the cache entries and write the output */
	for ( size_t block = 0; block < blocks; block++ ) {
		size_t row = 0;
		for (; row < block_size * (block + 1) && row < total_rows; row ++) {
			/* read in the current row from the root file */
			measurement_tree->GetEntry(row);
			/* copy the data from the row buffer into the block buffer */
			for ( size_t i = 0; i < data_columns.size(); i ++) {
				m_block_buffer[i + (row % block_size) * data_columns.size()] = m_data[i];
			}
			/* generate the cache key from the entries */
			CacheKey row_cache_key;
			if (event_mode) {
				row_cache_key = {e_chip, half, e_channel};
				row_cache_key = transform_event_row_to_cache_key(row_cache_key);
			} else {
				row_cache_key = {chip, channel, channeltype};
			}
			/* get the entries from the channel cache if there are any */
			if ( channel_cache ) {
				std::vector<int> &curr_config = channel_config[row_cache_key];
				for ( size_t i = 0; i < channel_columns.size(); i++ ) {
					c_config_data[i + (row % block_size) * channel_columns.size()] = curr_config[i];
				}
			}
			/* get the entries from the half_wise cache if there are any */
			if ( half_wise_cache ) {
				HalfWiseCacheKey hw_key = calc_half_wise_cache_key(row_cache_key);
				std::vector<int> &curr_config = half_wise_config[hw_key];
				for ( size_t i = 0; i < half_wise_columns.size(); i++ ) {
					hw_config_data[i + (row % block_size) * half_wise_columns.size()] = curr_config[i];
				}
			}
			/* get the entries from the global cache if there are any */
			if ( global_cache ) {
				GlobalCacheKey g_key = calc_global_cache_key(row_cache_key);
				std::vector<int> &curr_config = global_config[g_key];
				for ( size_t i = 0; i < global_columns.size(); i++ ) {
					g_config_data[i + (row % block_size) * global_columns.size()] = curr_config[i];
				}
			}
		}
		size_t write_row_count = 0;
		if ( row == total_rows )
			write_row_count = row % block_size;
		else
			write_row_count = block_size;
		write_to_block(measurement_block, axis1, write_row_count, (void *)m_block_buffer);
		if (channel_cache) write_to_block(channel_config_block, axis1, write_row_count, c_config_data);
		if (half_wise_cache) write_to_block(half_wise_config_block, axis1, write_row_count, hw_config_data);
		if (global_cache) write_to_block(global_config_block, axis1, write_row_count, g_config_data);

	}
	/* clean up the existing data structures */
	//measurement_tree->Close();
	H5Dclose(axis0);
	H5Dclose(axis1);
	H5Dclose(measurement_block);
	free(m_block_buffer);
	free(m_data);
	if (channel_cache) {
		H5Dclose(channel_config_block);
		free(c_config_data);
	}
	if (half_wise_cache) {
		H5Dclose(half_wise_config_block);
		free(hw_config_data);
	}
	if (global_cache) {
		H5Dclose(global_config_block);
		free(g_config_data);
	}
	return 0;
}
