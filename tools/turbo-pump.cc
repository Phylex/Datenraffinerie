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
	hid_t output = create_merge_output_file(output_path, group_name, input_file_paths[0]);
	for (size_t i = 1; i < input_file_paths.size(); i++) {
		try {
			append_file(output, group_name, input_file_paths[i]);
		} catch (std::runtime_error e) {
			std::cout << "Runtime error appending file: " << input_file_paths[i] << std::endl << e.what() << std::endl;
			exit(EXIT_FAILURE);
		}
	}
}
