#include "include/hdf-utils.h"

herr_t create_utf8_attribute(hid_t root_id, std::string name, std::string value) {
	hid_t attribute_space_id;
	hid_t datatype_id;
	hid_t attribute_id;
	herr_t status;

	// create attribute ID
	attribute_space_id = H5Screate(H5S_SCALAR);
	datatype_id = H5Tcopy(H5T_C_S1);
	H5Tset_cset(datatype_id, H5T_CSET_UTF8);
	H5Tset_size(datatype_id, value.size());
	
	// create actual attribute
	attribute_id = H5Acreate(root_id, name.c_str(),
							 datatype_id, attribute_space_id,
							 H5P_DEFAULT, H5P_DEFAULT
							);
	status = H5Awrite(attribute_id, datatype_id, value.c_str());

	//close the attribute
	if (status != 0) std::cout << status << std::endl;
	status = H5Aclose(attribute_id);
	if (status != 0) std::cout << status << std::endl;
	status = H5Sclose(attribute_space_id);
	return status;
}


herr_t create_empty_utf8_attribute(hid_t root_id, std::string attr_name) {
	herr_t status;
	hid_t datatype_id;
	hid_t attribute_space_id;
	hid_t attribute_id;
	attribute_space_id = H5Screate(H5S_NULL);
	datatype_id = H5Tcopy(H5T_C_S1);
	H5Tset_cset(datatype_id, H5T_CSET_UTF8);
	attribute_id = H5Acreate(root_id, attr_name.c_str(),
							datatype_id, attribute_space_id,
							H5P_DEFAULT, H5P_DEFAULT);
	status = H5Aclose(attribute_id);
	if (status != 0) std::cout << status << std::endl;
	status = H5Sclose(attribute_space_id);
	return status;
}

// make an array that contains the strings at the right locations
std::vector<char> make_h5_compat_string(std::vector<std::string> strings, size_t str_size) {
	std::vector<char> c_strs;
	for (auto &str: strings) {
		for (size_t i=0; i < str.size(); i++) {
			c_strs.push_back(str.c_str()[i]);
		}
		c_strs.push_back(0);
		for (size_t i=0; i< str_size - str.size() - 1; i++) {
			c_strs.push_back(0);
		}
	}
	return c_strs;
}

void create_axes(hid_t root_id, hid_t *axis0_id, hid_t *axis1_id) {
	/* set the parameters for the axis 0 */
	hsize_t ndims = 1;
	hsize_t dimensions[] = {0};
	hsize_t max_dimensions[] = {H5S_UNLIMITED};
	hsize_t chunk_dimensions[] = {5};
	int exdim = 0;
	long transposed = 1;
	std::vector<char> dummy_data;

	/* create the actual axis in the dataset */
	create_utf8_attribute(root_id, "axis0_variety", "regular");
	hid_t datatype = H5Tcopy(H5T_C_S1);
	H5Tset_size(datatype, 50);
	*axis0_id = create_dataset<char>(root_id, "axis0", datatype, ndims, dimensions, max_dimensions, chunk_dimensions, 0, dummy_data);
	create_utf8_attribute(*axis0_id, "CLASS", "EARRAY");
	create_numeric_attribute<int>(*axis0_id, "EXTDIM", H5T_STD_I32LE, &exdim);
	create_empty_utf8_attribute(*axis0_id, "TITLE");
	create_utf8_attribute(*axis0_id, "VERSION", "1.1");
	create_utf8_attribute(*axis0_id, "kind", "string");
	create_utf8_attribute(*axis0_id, "name", "columns");
	create_numeric_attribute<long>(*axis0_id, "transposed", H5T_STD_I64LE, &transposed);
	H5Tclose(datatype);

	//create an empty axis 1 so that it can be filled
	create_utf8_attribute(root_id, "axis1_variety", "regular");
	std::vector<int> axis1_data;
	dimensions[0] = 0;
	chunk_dimensions[0] = 200000;
	datatype = H5Tcopy(H5T_STD_I32LE);
	*axis1_id = create_dataset<int>(root_id, "axis1", datatype, ndims, dimensions, max_dimensions, chunk_dimensions, 0, axis1_data);
	create_utf8_attribute(*axis1_id, "CLASS", "EARRAY");
	create_numeric_attribute<int>(*axis1_id, "EXTDIM", H5T_STD_I32LE, &exdim);
	create_empty_utf8_attribute(*axis1_id, "TITLE");
	create_utf8_attribute(*axis1_id, "VERSION", "1.1");
	create_utf8_attribute(*axis1_id, "kind", "string");
	create_utf8_attribute(*axis1_id, "name", "values");
	create_numeric_attribute<long>(*axis1_id, "transposed", H5T_STD_I64LE, &transposed);
}


hid_t add_block(hid_t group_id, hid_t value_datatype, hid_t axis0, std::vector<std::string> block_items) {
	/* get the number of blocks already in the group and create the attributes for the
	 * new block in the group */
	long block_count;
	hid_t nblocks;
	nblocks = H5Aopen(group_id, "nblocks", H5P_DEFAULT);
	H5Aread(nblocks, H5T_STD_I64LE, (void *)(&block_count));
	std::stringstream block_name;
	block_name << "block" << block_count << "_items_variety";
	block_count ++;
	H5Awrite(nblocks, H5T_STD_I64LE, &block_count);
	block_count --;
	H5Aclose(nblocks);
	create_utf8_attribute(group_id, block_name.str(), "regular");
	/* create the blockx_items dataset */
	block_name.str("");
	block_name << "block" << block_count << "_items";
	hid_t item_datatype = H5Tcopy(H5T_C_S1);
	H5Tset_size(item_datatype, 50);
	const hsize_t drank = 1;
	const hsize_t item_dim[] = {block_items.size()};
	hid_t item_dataspace = H5Screate_simple(drank, item_dim, item_dim);
	hid_t item_dataset = H5Dcreate(group_id, block_name.str().c_str(), item_datatype,
								   item_dataspace, H5P_DEFAULT, H5P_DEFAULT, H5P_DEFAULT);
	hsize_t column_count = block_items.size();
	hid_t mem_space = H5Screate_simple(1, &column_count, NULL);
	std::vector<char> block_item_string = make_h5_compat_string(block_items, 50);
	H5Dwrite(item_dataset, item_datatype, mem_space, item_dataspace, H5P_DEFAULT, block_item_string.data());
	create_utf8_attribute(item_dataset, "CLASS", "ARRAY");
	create_utf8_attribute(item_dataset, "FLAVOUR", "numpy");
	create_empty_utf8_attribute(item_dataset, "TITLE");
	create_utf8_attribute(item_dataset, "VERSION", "2.4");
	create_utf8_attribute(item_dataset, "kind", "string");
	create_utf8_attribute(item_dataset, "name", "N.");
	long transposed = 1;
	create_numeric_attribute<long>(item_dataset, "transposed", H5T_STD_I64LE, &transposed);
	H5Dclose(item_dataset);
	H5Sclose(item_dataspace);
	H5Tclose(item_datatype);

	/* create an empty extensible dataset for the block values */
	block_name.str("");
	block_name << "block" << block_count << "_values";
	const hsize_t vdrank = 2;
	hsize_t val_dim[] = {0, block_items.size()};
	hsize_t max_dim[] = {H5S_UNLIMITED, block_items.size()};
	hsize_t chunk_dim[] = {1000, block_items.size()};
	hid_t val_dataset;
	if (H5T_INTEGER == H5Tget_class(value_datatype)) {
		std::vector<int> dummy_data;
		val_dataset = create_dataset<int>(group_id, block_name.str(), value_datatype,
										  vdrank, val_dim, max_dim, chunk_dim, 0, dummy_data);
	} else if (H5T_FLOAT == H5Tget_class(value_datatype)) {
		std::vector<float> dummy_data;
		val_dataset = create_dataset<float>(group_id, block_name.str(), value_datatype,
											vdrank, val_dim, max_dim, chunk_dim, 0, dummy_data);
	} else {
		std::cout << "The block is being created for an unsupported datatype" << std::endl;
		exit(EXIT_FAILURE);
	}
	create_utf8_attribute(val_dataset, "CLASS", "ARRAY");
	create_utf8_attribute(val_dataset, "FLAVOUR", "numpy");
	create_empty_utf8_attribute(val_dataset, "TITLE");
	create_utf8_attribute(val_dataset, "VERSION", "2.4");
	create_utf8_attribute(val_dataset, "kind", "string");
	create_utf8_attribute(val_dataset, "name", "N.");
	create_numeric_attribute<long>(val_dataset, "transposed", H5T_STD_I64LE, &transposed);

	/* extend the axis0 data (columns) */
	/* figure out current extent */
	hid_t ax0_dataspace = H5Dget_space(axis0);
	hsize_t ax0rank = H5Sget_simple_extent_ndims(ax0_dataspace);
	hsize_t *ax_dim = (hsize_t *)malloc(ax0rank * sizeof(hsize_t));
	H5Sget_simple_extent_dims(ax0_dataspace, ax_dim, NULL);
	hsize_t old_dim = ax_dim[0];

	/* extend the axis0 */
	ax_dim[0] += block_items.size();
	herr_t status = H5Dextend(axis0, ax_dim);
	if (status != 0) std::cout << status << std::endl;
	H5Sclose(ax0_dataspace);

	/* copy the data from the vector of block_item names into the file */
	ax0_dataspace = H5Dget_space(axis0);
	hsize_t start[] = {old_dim};
	hsize_t count[] = {ax_dim[0] - old_dim};
	H5Sselect_hyperslab(ax0_dataspace, H5S_SELECT_SET, start, NULL, count, NULL);
	hid_t axis0_type = H5Dget_type(axis0);
	hsize_t string_length = H5Tget_size(axis0_type);
	H5Dwrite(axis0, axis0_type, mem_space, ax0_dataspace, H5P_DEFAULT, block_item_string.data());
	H5Sclose(ax0_dataspace);
	H5Sclose(mem_space);
	H5Tclose(axis0_type);
	free(ax_dim);
	return val_dataset;
}

hid_t set_up_file(hid_t file_id, std::string group_name) {
	/* set file wide attributes */
	create_utf8_attribute(file_id, "CLASS", "GROUP");
	create_utf8_attribute(file_id, "PYTABLES_FORMAT_VERSION", "2.1");
	create_utf8_attribute(file_id, "VERSION", "1.0");
	create_empty_utf8_attribute(file_id, "TITLE");

	/* create the groud and the properties of the group */
	hid_t group_id = H5Gcreate2(file_id, "/data", H5P_DEFAULT, H5P_DEFAULT, H5P_DEFAULT);
	create_utf8_attribute(group_id, "CLASS", "GROUP");
	create_utf8_attribute(group_id, "VERSION", "1.0");
	create_empty_utf8_attribute(group_id, "TITLE");
	create_utf8_attribute(group_id, "encoding", "UTF-8");
	create_utf8_attribute(group_id, "errors", "strict");
	long attr_data = 0;
	create_numeric_attribute<long>(group_id, "nblocks", H5T_STD_I64LE, &attr_data);
	attr_data = 2;
	create_numeric_attribute<long>(group_id, "ndim", H5T_STD_I64LE, &attr_data);
	create_utf8_attribute(group_id, "pandas_type", "frame");
	create_utf8_attribute(group_id, "pandas_version", "0.15.2");
	return group_id;
}

/* write a number of rows to the block indicated by ds_block_id from data */
/* the caller must make sure that data is large enough to hold all the data indicated
 * by the number of columns of the block and the number of rows indicated */
void write_to_block(hid_t ds_block_id, hid_t axis1_id, size_t rows, void *data) {
	hid_t block_datatype = H5Dget_type(ds_block_id);
	
	/* get the dimensions of the block */
	hid_t block_dataspace = H5Dget_space(ds_block_id);
	hsize_t ds_rank = H5Sget_simple_extent_ndims(block_dataspace);
	hsize_t *ds_dims = (hsize_t *)malloc(ds_rank * sizeof(hsize_t));
	hsize_t *max_ds_dims = (hsize_t *)malloc(ds_rank * sizeof(hsize_t));
	ds_rank = H5Sget_simple_extent_dims(block_dataspace, ds_dims, max_ds_dims);
	H5Sclose(block_dataspace);

	/* exit if there is no space in the dataframe */
	if (ds_dims[0] + rows > max_ds_dims[0]) {
		std::cout << "Adding rows to dataset extends beyond the maximal dimensions" << std::endl;
		free(ds_dims);
		free(max_ds_dims);
		H5Tclose(block_datatype);
		exit(EXIT_FAILURE);
	}
	free(max_ds_dims);

	/* initialize the size of the region in memmory */
	hsize_t *mem_ds_dims = (hsize_t *)malloc(ds_rank * sizeof(hsize_t));
	mem_ds_dims[0] = rows;
	for (size_t i = 1; i < ds_rank; i++) {
		mem_ds_dims[i] = ds_dims [i];
	}
	
	/* extend the block and write data to it */
	hsize_t start_row = ds_dims[0];
	ds_dims[0] += rows;
	H5Dextend(ds_block_id, ds_dims);
	block_dataspace = H5Dget_space(ds_block_id);

	/* reuse ds_dims as start point for the hyperslab */
	ds_dims[0] = start_row;
	for (int i = 1; i < ds_rank; i++ ) {
		ds_dims[i] = 0;
	}

	/* select the block of memmory in the file that corresponds to the added space */
	H5Sselect_hyperslab(block_dataspace, H5S_SELECT_SET, ds_dims, NULL, mem_ds_dims, NULL);

	/* create the data space description for the memmory space*/
	hid_t mem_space = H5Screate_simple(ds_rank, mem_ds_dims, NULL);

	/* compy the data over from memmory to file space */
	H5Dwrite(ds_block_id, block_datatype, mem_space, block_dataspace, H5P_DEFAULT, data);
	
	H5Sclose(mem_space);

	/* extend axis1 if necessary */
	hid_t axis_dataspace = H5Dget_space(axis1_id);
	hid_t axis_datatype = H5Dget_type(axis1_id);
	hsize_t ax_rank = H5Sget_simple_extent_ndims(axis_dataspace);
	hsize_t *original_ax_dims = (hsize_t *)malloc(ax_rank * sizeof(hsize_t));
	hsize_t *ax_mem_dims = (hsize_t *)malloc(ax_rank * sizeof(hsize_t));
	H5Sget_simple_extent_dims(axis_dataspace, original_ax_dims, NULL);
	H5Sget_simple_extent_dims(axis_dataspace, ax_mem_dims, NULL);
	ax_mem_dims[0] = rows;
	H5Sclose(axis_dataspace);

	if (original_ax_dims[0] < ds_dims[0] + rows) {
		hsize_t old_ax_dims = original_ax_dims[0];
		original_ax_dims[0] = ds_dims[0] + rows;
		H5Dextend(axis1_id, original_ax_dims);
		original_ax_dims[0] = old_ax_dims;
		axis_dataspace = H5Dget_space(axis1_id);
		hsize_t *new_ax_dims = (hsize_t *)malloc(ax_rank * sizeof(hsize_t));
		H5Sget_simple_extent_dims(axis_dataspace, new_ax_dims, NULL);
		H5Sselect_hyperslab(axis_dataspace, H5S_SELECT_SET, original_ax_dims, NULL, ax_mem_dims, NULL);
		hid_t axis_memspace = H5Screate_simple(ax_rank, ax_mem_dims, NULL);
		std::vector<int> buffer;
		buffer.reserve(new_ax_dims[0] - old_ax_dims);
		for (long j = old_ax_dims; j < new_ax_dims[0]; j ++) {
			buffer.push_back(j);
		}
		free(new_ax_dims);
		H5Dwrite(axis1_id, axis_datatype, axis_memspace, axis_dataspace, H5P_DEFAULT, buffer.data());
		H5Sclose(axis_memspace);
		H5Sclose(axis_dataspace);
	}
	/* tidy up */
	H5Tclose(axis_datatype);
	free(original_ax_dims);
	free(ax_mem_dims);
	free(ds_dims);
	free(mem_ds_dims);
	H5Sclose(block_dataspace);
	H5Tclose(block_datatype);
}
