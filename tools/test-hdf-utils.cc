#include "include/hdf-utils.h"
#include "include/exceptions.h"
#define PD_FNAME "test_pandas_compat.h5"
#define MERGE_SRC_1 "merge_input_1.h5"
#define MERGE_SRC_2 "merge_input_2.h5"
#define MERGE_OUT "merge_output_3.h5"

int main() {
	std::cout << "Create pandas test file" << std::endl;
	/* create a file to test pandas import with */
	hid_t file_id, group_id, axis0, axis1;
	file_id = H5Fcreate(PD_FNAME, H5F_ACC_TRUNC, H5P_DEFAULT, H5P_DEFAULT);
	group_id = set_up_file(file_id, "data");
	std::vector<std::string> columns = { "this", "that", "something"};
	std::vector<std::string> additional_columns = { "other", "than", "else"};
	create_axes(group_id, &axis0, &axis1);
	hid_t blk0_ds = add_block(group_id, H5T_STD_I32LE, columns);
	hid_t blk1_ds = add_block(group_id, H5T_STD_I32LE, additional_columns);
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
	for (size_t j=0; j < rows; j ++) {
		for (size_t i=0; i < columns.size(); i ++) {
			values[j*columns.size() + i] = (rows - j)*10 + i;
		}
	}
	write_to_block(blk0_ds, axis1, rows, (void *)values.data());
	write_to_block(blk1_ds, axis1, rows, (void *)values.data());
	/* clean up */
	H5Dclose(blk0_ds);
	H5Dclose(blk1_ds);
	H5Dclose(axis0);
	H5Dclose(axis1);
	H5Gclose(group_id);
	H5Fclose(file_id);

	std::cout << "Create first merge test input file" << std::endl;
	/* create the first input file for the merge test */
	file_id = H5Fcreate(MERGE_SRC_1, H5F_ACC_TRUNC, H5P_DEFAULT, H5P_DEFAULT);
	group_id = set_up_file(file_id, "data");
	create_axes(group_id, &axis0, &axis1);
	blk0_ds = add_block(group_id, H5T_STD_I32LE, columns);
	blk1_ds = add_block(group_id, H5T_STD_I32LE, additional_columns);
	for (size_t j=0; j < rows; j ++) {
		for (size_t i=0; i < columns.size(); i ++) {
			values[i + j * columns.size()] = j*10 + i;
		}
	}
	write_to_block(blk0_ds, axis1, rows, (void *)values.data());
	write_to_block(blk1_ds, axis1, rows, (void *)values.data());
	/* clean up */
	H5Dclose(blk0_ds);
	H5Dclose(blk1_ds);
	H5Dclose(axis0);
	H5Dclose(axis1);
	H5Gclose(group_id);
	H5Fclose(file_id);

	std::cout << "Create second merge test input file" << std::endl;
	/* create the second input file for the merge test */
	file_id = H5Fcreate(MERGE_SRC_2, H5F_ACC_TRUNC, H5P_DEFAULT, H5P_DEFAULT);
	group_id = set_up_file(file_id, "data");
	create_axes(group_id, &axis0, &axis1);
	blk0_ds = add_block(group_id, H5T_STD_I32LE, columns);
	blk1_ds = add_block(group_id, H5T_STD_I32LE, additional_columns);
	for (size_t j=0; j < rows; j ++) {
		for (size_t i=0; i < columns.size(); i ++) {
			values[j*columns.size() + i] = (rows - j)*10 + i;
		}
	}
	write_to_block(blk0_ds, axis1, rows, (void *)values.data());
	write_to_block(blk1_ds, axis1, rows, (void *)values.data());
	/* clean up */
	H5Dclose(blk0_ds);
	H5Dclose(blk1_ds);
	H5Dclose(axis0);
	H5Dclose(axis1);
	H5Gclose(group_id);
	H5Fclose(file_id);

	std::cout << "Test merge functions" << std::endl;
	hid_t out_file_id = create_merge_output_file(MERGE_OUT, "data", MERGE_SRC_1);
	append_file(out_file_id, "data", MERGE_SRC_2);
	H5Fclose(out_file_id);
	return 0;
}
