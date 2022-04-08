#include "include/hdf-utils.h"
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
	for (size_t j=0; j < rows; j ++) {
		for (size_t i=0; i < columns.size(); i ++) {
			values[i*columns.size() + j] = (rows - j)*10 + i;
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
	blk0_ds = add_block(group_id, H5T_STD_I32LE, axis0, columns);
	blk1_ds = add_block(group_id, H5T_STD_I32LE, axis0, additional_columns);
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
	blk0_ds = add_block(group_id, H5T_STD_I32LE, axis0, columns);
	blk1_ds = add_block(group_id, H5T_STD_I32LE, axis0, additional_columns);
	for (size_t j=0; j < rows; j ++) {
		for (size_t i=0; i < columns.size(); i ++) {
			values[i*columns.size() + j] = (rows - j)*10 + i;
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
	/* create the basic structure for the output file */
	hid_t out_file_id = H5Fcreate(MERGE_OUT, H5F_ACC_TRUNC, H5P_DEFAULT, H5P_DEFAULT);
	hid_t out_group_id = set_up_file(out_file_id, "data");
	hid_t out_axis0, out_axis1;
	create_axes(out_group_id, &out_axis0, &out_axis1);
	std::cout << "Get first input file to merge" << std::endl;
	hid_t in_file = H5Fopen(MERGE_SRC_1, H5F_ACC_RDONLY, H5P_DEFAULT);
	hid_t in_group = H5Gopen(in_file, "data", H5P_DEFAULT);
	hid_t nblocks;
	long long block_count = 0;
	if (H5Aexists(in_group, "nblocks") > 0) {
		nblocks = H5Aopen(in_group, "nblocks", H5P_DEFAULT);
		H5Aread(nblocks, H5T_STD_I64LE, &block_count);
	}
	H5Aclose(nblocks);
	std::vector<std::vector<std::string>> in_column_blocks;
	hid_t *in_block_data_type = new hid_t[block_count];
	size_t *in_block_rank = new size_t[block_count];
	hsize_t **in_block_dim = new hsize_t*[block_count];
	hid_t *in_block_dataspace = new hid_t[block_count];
	hid_t *in_block_dataset = new hid_t[block_count];
	hid_t *out_block_datasets = new hid_t[block_count];
	hid_t *out_block_dataspace = new hid_t[block_count];
	/* for every block in the first input file create the block in the output file and copy the data over */
	for ( size_t i = 0; i < block_count; i ++) {
		in_column_blocks.push_back(get_columns_in_block(in_group, i));
		std::cout << "Columns in the first block are: " << std::endl;
		for (auto col: in_column_blocks[i]) {
			std::cout << col << " ";
		}
		std::cout << std::endl;
		in_block_dataset[i] = get_block_dataset(in_group, i);
		in_block_data_type[i] = H5Dget_type(in_block_dataset[i]);
		in_block_dataspace[i] = H5Dget_space(in_block_dataset[i]);
		in_block_rank[i] = get_dimensions(in_block_dataspace[i], &(in_block_dim[i]), NULL);
		std::cout << "block_rank: " << in_block_rank[i] << " block_dim: " << in_block_dim[i] << std::endl;
		out_block_datasets[i] = add_block(out_group_id, in_block_data_type[i], out_axis0, in_column_blocks[i]);
		out_block_dataspace[i] = H5Dget_space(out_block_datasets[i]);
		hsize_t element_count = 1;
		for (int j = 0; j < in_block_rank[i]; j ++) {
			element_count *= in_block_dim[i][j];
		}
		void *buffer = malloc(element_count * H5Tget_size(in_block_data_type[i]));
		H5Dread(in_block_dataset[i], in_block_data_type[i], in_block_dataspace[i], in_block_dataspace[i], H5P_DEFAULT, buffer);
		write_to_block(out_block_datasets[i], out_axis1, in_block_dim[i][0], buffer);
		free(buffer);
	}

	/* clean up */
	H5Dclose(out_axis1);
	H5Dclose(out_axis0);
	H5Gclose(out_group_id);
	H5Fclose(out_file_id);
	return 0;
}
