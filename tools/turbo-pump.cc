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
		->required()
		->check(CLI::ExistingPath);
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

	hid_t output = H5Fcreate(output_path.c_str(), H5F_ACC_TRUNC, H5P_DEFAULT, H5P_DEFAULT);
	hid_t group_id = set_up_file(output, group_name.c_str());
	hid_t axis0 = 0;
	hid_t axis1 = 0;
	create_axes(group_id, &axis0, &axis1);
}
