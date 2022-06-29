#include "include/hdf-utils.h"
#include "include/exceptions.h"
#define PD_FNAME "test_pandas_compat.h5"
#define MERGE_SRC_1 "merge_input_1.h5"
#define MERGE_SRC_2 "merge_input_2.h5"
#define MERGE_OUT "merge_output_3.h5"
#define TABLES_OUT1 "tables_test_1.h5"
#define TABLES_OUT2 "tables_test_2.h5"
#define MERGED_TABLES_OUT "tables_test_merged.h5"


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
	
	std::cout << "Test pytables functions" << std::endl;
	/* prepare data and type for the merge */
	std::vector<hid_t> col_types = {H5T_NATIVE_INT, H5T_NATIVE_INT, H5T_NATIVE_INT, H5T_NATIVE_FLOAT, H5T_NATIVE_FLOAT};
	std::vector<std::string> col_names = {"this", "that", "something", "else", "other"};
	hid_t table_type = create_compund_datatype(col_names, col_types);
	void *buffer = malloc(100 * H5Tget_size(table_type));
	for (size_t i = 0; i < 100; i++) {
		char *row = (char *)(buffer) + i * H5Tget_size(table_type);
		((int *)(row))[0] = i;
		((int *)(row))[1] = 100 -i;
		((int *)(row))[2] = i;
		((float *)((int *)(row) + 3))[0] = 1./100. * i;
		((float *)((int *)(row) + 3))[1] = 1./100. * (100 - i);
	}

	hid_t t1_file = create_pytables_file(TABLES_OUT1);
	hid_t t1_group = create_pytables_group(t1_file, "data", "test the pytables interface");
	hid_t t1 = create_pytables_table(t1_group, "measurements", table_type, 100);
	write_buffer_to_pytable(t1, table_type, 100, buffer);
	write_buffer_to_pytable(t1, table_type, 60, buffer);
	
	hid_t t2_file = create_pytables_file(TABLES_OUT2);
	hid_t t2_group = create_pytables_group(t2_file, "data", "test the pytables interface");
	hid_t t2 = create_pytables_table(t2_group, "measurements", table_type, 100);
	write_buffer_to_pytable(t2, table_type, 50, buffer);
	
	hid_t tm_file = create_pytables_file(MERGED_TABLES_OUT);
	hid_t tm_group = create_pytables_group(tm_file, "data", "test the pytables interface");
	hid_t tm = create_pytables_table(tm_group, "measurements", table_type, 100);

	merge_tables(tm_file, t1_file, "data", "measurements", 10);
	merge_tables(tm_file, t2_file, "data", "measurements", 12);
	free(buffer);
	H5Tclose(table_type);
	H5Dclose(t1);
	H5Dclose(t2);
	H5Dclose(tm);
	H5Gclose(t1_group);
	H5Gclose(t2_group);
	H5Gclose(tm_group);
	H5Fclose(t1_file);
	H5Fclose(t2_file);
	H5Fclose(tm_file);
	return 0;
}
