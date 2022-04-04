#include "include/hdf-utils.h"
#define FNAME "test_hdf_out.h5"

int main() {
	hid_t file_id, group_id, axis0, axis1;
	herr_t status;
	
	file_id = H5Fcreate(FNAME, H5F_ACC_TRUNC, H5P_DEFAULT, H5P_DEFAULT);
	group_id = set_up_file(file_id, "data");
	std::vector<std::string> columns = { "this", "that", "something"};
	std::vector<std::string> additional_columns = { "other", "than", "else"};
	create_axes(group_id, &axis0, &axis1);
	hid_t blk0_ds = add_block(group_id, H5T_STD_I32LE, axis0, columns);
	hid_t blk1_ds = add_block(group_id, H5T_STD_I32LE, axis0, additional_columns);
	size_t rows = 100;
	std::vector<int> values;
	values.reserve(rows * columns.size());
	for (size_t j=0; j < rows; j ++) {
		for (size_t i=0; i < columns.size(); i ++) {
			values.push_back(j*10 + i);
		}
	}
	write_to_block(blk0_ds, axis1, rows, (void *)values.data());
	write_to_block(blk1_ds, axis1, rows, (void *)values.data());
	status = H5Gclose(group_id);
	std::cout << status << std::endl;
	status = H5Fclose(file_id);
	std::cout << status << std::endl;
	return 0;
}
