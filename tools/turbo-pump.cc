#include "include/hdf-utils.h"
#include "include/CLI11.hpp"
#include <iostream>
#include <stdlib.h>

int main(int argc, char **argv) {
	CLI::App app {"Merge the data from multiple hdf-files into a single file"};
	std::vector<std::string> input_file_paths;
	std::string group_name;
	std::string output_path;
	size_t block_size;

	app.add_option("-i", input_file_paths, "paths to the files to be merged")
		->required()
		->check(CLI::ExistingFile);
	app.add_option("-o", output_path, "path to the file containing the merged data")
		->required();
	app.add_option("-b", block_size, "Set the size of a chunk in the hdf file")
		->default_val(1000000);
	app.add_option("-g", group_name, "Specify the name of the group holding the dataset in the in and output")
		->default_val("data");

	try {
		CLI11_PARSE(app, argc, argv);
	} catch (CLI::ValidationError e) {
		std::cout << "Invalid arguments:" << std::endl << e.what() << std::endl;
		exit(EXIT_FAILURE);
	}
	if (input_file_paths.size() <= 1) {
		std::cout << "More than one input file needs to be specified" << std::endl;
		exit(EXIT_FAILURE);
	}
	hid_t input_table_type = get_pytable_type(input_file_paths[0], group_name, "measurements");
	hid_t output_file = create_pytables_file(output_path);
	hid_t output_group = create_pytables_group(output_file, group_name, "");
	hid_t output_talbe = create_pytables_table(output_group, "measurements", input_table_type, block_size, 2);
	for (size_t i = 0; i < input_file_paths.size(); i++) {
		try {
			hid_t in_file = H5Fopen(input_file_paths[i].c_str(), H5P_DEFAULT, H5P_DEFAULT);
			merge_tables(output_file, in_file, group_name, "measurements", block_size);
		} catch (std::runtime_error e) {
			std::cout << "Runtime error appending file: " << input_file_paths[i] << std::endl << e.what() << std::endl;
			exit(EXIT_FAILURE);
		}
	}
}
