#include "include/CLI11.hpp"
#include "include/yaml-tools.h"
#include "include/hgcroc_caching.h"
#include "include/root-tools.h"
#include "include/hdf-utils.h"
#include <H5Spublic.h>
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
	bool iterable;
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
	app.add_option("-t", iterable, "specify if the output file should be iterable");

	/* parse the options */
	try {
		CLI11_PARSE(app, argc, argv);
	} catch (CLI::ValidationError e) {
		std::cout << "Invalid arguments " << e.what() << std::endl;
		exit(EXIT_FAILURE);
	}

	/* open the (overlay) config */
	YAML::Node run_config;	// this is the config that will hold the final config
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
		run_config = default_config;
	} else {
		run_config = overlay_config;
	}

	/* get the tree from the root file containing the data */
	bool event_mode;
	TFile *Measurement;
	TTree *measurement_tree = openRootTree(Measurement, data_file_path, &event_mode);
	std::vector<std::string> data_columns = filter_measurement_columns(event_mode, columns);
	std::vector<std::string> config_columns;
	/* filter out the columns needed for the configuration */
	for (auto column: columns) {
		if (column_type.find(column) != column_type.end()) {
			config_columns.push_back(column);
		}
	}

	/* create the output file and set it up */
	hid_t data_file = create_pytables_file(output_path);
	hid_t data_group = create_pytables_group(data_file, "data", "");
	hid_t table_type = create_compound_datatype_form_columns(data_columns, config_columns, event_mode);
	hid_t table = create_pytables_table(data_group, "measurements", table_type, 100000);

	/* create the cache from the rows of the table */
	std::map<CacheKey, std::vector<long long>> cache = generate_hgcroc_config_cache<long long>(run_config, columns);
	/* create the block buffer that is filed with the data from the root file and the config 
	 * before being written to the hdf file */
	void *m_block_buffer= malloc(block_size * H5Tget_size(table_type));
	for (size_t i = 0; i < block_size * H5Tget_size(table_type); i++) {
		*((char *)m_block_buffer + i) = 0;
	}

	/* set up the arrays to buffer the data between the root and hdf files */
	hgcroc_data d_buffer;
	hgcroc_summary_data summary_buffer;
	
	/* set up the  values holding the cache key info */
	unsigned int chip;
	unsigned short channel;
	unsigned short channeltype;
	int e_chip;
	int half;
	int e_channel;
	void *key_chip_source = NULL;
	void *key_channel_source = NULL;
	void *key_half_source = NULL;
	/* get the size of the data in the root file */
	size_t total_rows = measurement_tree->GetEntries();
	size_t blocks = total_rows / block_size + 1;
	/* link the entries of the keys to the variables to build the caching key */
	if ( event_mode ) {
		measurement_tree->SetBranchAddress("chip", &e_chip);
		measurement_tree->SetBranchAddress("half", &half);
		measurement_tree->SetBranchAddress("channel", &e_channel);
		key_channel_source = &e_channel;
		key_chip_source = &e_chip;
		key_half_source = &half;
	} else {
		measurement_tree->SetBranchAddress("chip", &chip);
		measurement_tree->SetBranchAddress("channeltype", &channeltype);
		measurement_tree->SetBranchAddress("channel", &channel);
		key_channel_source = &channel;
		key_chip_source = &chip;
		key_half_source = &channeltype;
	}

	/* link the elements of the root tree to the small local buffer */
	for (size_t i = 0; i < data_columns.size(); i++) {
		void *data_member_pointer;
		if (event_mode) {
			data_member_pointer = d_buffer.get_pointer_to_entry(data_columns[i].c_str());
		} else {
			data_member_pointer = summary_buffer.get_pointer_to_entry(data_columns[i].c_str());
		}
		if (data_member_pointer == NULL) {
			std::cout << "Invalid data column passed to fracker" << std::endl;
			exit(EXIT_FAILURE);
		}
		if (data_columns[i] == "chip") key_chip_source = data_member_pointer;
		else if (data_columns[i] == "channel") key_channel_source = data_member_pointer;
		else if (data_columns[i] == "half") key_half_source = data_member_pointer;
		else if (data_columns[i] == "channeltype") key_half_source = data_member_pointer;
		measurement_tree->SetBranchAddress(data_columns[i].c_str(), data_member_pointer);
	}

	/* run through the root file, retrieve the config from the cache entries and write the output */
	/* do this for every block */
	size_t row = 0;
	for ( size_t block = 0; block < blocks; block++ ) {
		/* copy all the data for this block into the buffer */
		for (; row < block_size * (block + 1) && row < total_rows; row ++) {
			/* read in the current row from the root file */
			measurement_tree->GetEntry(row);
			CacheKey key;
			if (event_mode) {
				key = CacheKey(*((int *)key_chip_source), *((int *)key_channel_source), *((int *)key_half_source));
				key = transform_event_row_to_cache_key(key);
			} else {
				key = CacheKey(*((int *)key_chip_source), *((short *)key_channel_source), *((short *)key_half_source));
			}
			if (!validate_key(key)) {
				std::cout << "Key is invalid. Chip=" << std::get<0>(key) << " Channel=" << std::get<1>(key) << " Type=" << std::get<2>(key) << std::endl;
				exit(EXIT_FAILURE);
			}
			/* copy the data from the root file and the config into the m_block_buffer */
			for ( size_t i = 0; i < H5Tget_nmembers(table_type);  i ++) {
				hid_t member_type = H5Tget_member_type(table_type, i);
				size_t member_size = H5Tget_size(member_type);
				char * member_name = H5Tget_member_name(table_type, i);
				H5Tclose(member_type);
				char *elem;
				if (i < data_columns.size()) {
					if (event_mode) {
						elem = (char *)d_buffer.get_pointer_to_entry(member_name);
					} else {
						elem = (char *)summary_buffer.get_pointer_to_entry(member_name);
					}
				} else {
					elem = (char *)&(cache[key].data()[i - data_columns.size()]);
				}
				for (int byteno = 0; byteno < member_size; byteno++) {
					// this is the actual copy step
					// the use of pointers is necessary to avoid lots of code to cast the members into the correct sizes
					*((char *)(m_block_buffer) + (row % block_size) * H5Tget_size(table_type) + H5Tget_member_offset(table_type, i) + byteno) = *(elem+byteno);
				}
				free(member_name);
			}
		}
		/* this value is needed to determine how much of the buffer needs to be written into the hdf file */
	  hsize_t write_row_count;
		if ( row == total_rows )
			write_row_count = row % block_size;
		else
			write_row_count = block_size;
		write_buffer_to_pytable(table, table_type, write_row_count, m_block_buffer);
	}
	/* clean up */
	free(m_block_buffer);
	H5Dclose(table);
	H5Tclose(table_type);
	H5Gclose(data_group); 
	H5Fclose(data_file);
	return 0;
}
