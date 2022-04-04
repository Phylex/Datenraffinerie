#include "include/CLI11.hpp"
#include "include/yaml-tools.h"
#include "include/hgcroc_caching.h"
#include "include/root-tools.h"
#include "include/hdf-utils.h"
#include <iostream>
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

	/* set up the options of the command */
	app.add_option("-dc", default_config_path, "default config of the target")
		->check(CLI::ExistingFile)
		->default_val("null");
	app.add_option("-rc", config_file_path, "Run configuration file")
		->required()
		->check(CLI::ExistingFile);
	app.add_option("-d", data_file_path, "root file containing the data")
		->required()
		->check(CLI::ExistingFile);
	app.add_option("-s", columns, "The selection of columns that should appear in the output data");
	app.add_option("-o", output_path, "path to the output containing the data and config specified");

	/* parse the options */
	CLI11_PARSE(app, argc, argv);

	/* open the (overlay) config */
	YAML::Node config;	// this is the config that will hold the final config
	YAML::Node overlay_config;
	try {
		overlay_config = YAML::LoadFile(config_file_path);
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

	/* generate the with the cache of the configuration */
	/* generate the channel wise config cache */
	std::vector<std::string> channel_columns = filter_channel_columns(columns);
	if (channel_columns.size() > 0 )
		std::map<CacheKey, std::vector<int>> channel_config = generate_hgcroc_chan_config_cache<int>(config, channel_columns);
	/* generate the half wise configuration cache */
	std::vector<ConfigKey> half_wise_columns = filter_half_wise_columns(columns);
	if (half_wise_columns.size() > 0 )
		std::map<HalfWiseCacheKey, std::vector<int>> half_wise_config_cache = generate_hgcroc_halfwise_config<int>(config, half_wise_columns);
	/* generate the global config cache */
	std::vector<ConfigKey> global_columns = filter_global_columns(columns);
	if (global_columns.size() > 0 )
		std::map<GlobalCacheKey, std::vector<int>> global_config_cache = generate_hgcroc_global_config<int>(config, half_wise_columns);

	/* get the tree from the root file containing the data */
	bool event_mode;
	TTree *measurement_tree = openRootTree(data_file_path, &event_mode);
	std::vector<std::string> data_columns = filter_measurement_columns(event_mode, columns);

	/* create the output file and create the blocks in the output file */
	hid_t output = H5Fcreate(output_path.c_str(), H5F_ACC_TRUNC, H5P_DEFAULT, H5P_DEFAULT);
	hid_t group_id = set_up_file(output, "data");
	hid_t axis0 = NULL;
	hid_t axis1 = NULL;
	hid_t measurement_block = NULL;
	hid_t channel_block = NULL;
	hid_t half_wise_block = NULL;
	hid_t global_block = NULL;
	create_axes(group_id, &axis0, &axis1);
	if ( data_columns.size() > 0 )
		hid_t measurement_block = add_block(group_id, H5T_NATIVE_FLOAT, axis0, data_columns);
	if ( channel_columns.size() > 0 )
		hid_t channel_block = add_block(group_id, H5T_STD_I32LE, axis0, channel_columns);
	if ( half_wise_columns.size() > 0 )
		hid_t half_wise_block = add_block(group_id, H5T_STD_I32LE, axis0, half_wise_columns);
	if ( global_columns.size() > 0 )
		hid_t global_block = add_block(group_id, H5T_STD_I32LE, axis0, global_columns);
	
	/* run through the root file, retrieve the config from the cache entries and write the output */
	return 0;
}
