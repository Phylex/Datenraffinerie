#include "include/hdf-utils.h"
#include "include/exceptions.h"

long get_block_count(hid_t group_id) {
	hid_t nblocks_attr;
	long block_count = 0;
	if (H5Aexists(group_id, "nblocks") > 0) {
		nblocks_attr = H5Aopen(group_id, "nblocks", H5P_DEFAULT);
		H5Aread(nblocks_attr, H5T_STD_I64LE, &block_count);
		H5Aclose(nblocks_attr);
	} else {
		throw std::runtime_error("nblocks Attribute can not be found in group");
	}
	return block_count;
}

size_t get_dimensions(hid_t dataspace, hsize_t **dims, hsize_t **maxdims) {
	size_t ds_rank;
	hsize_t *call_dims, *call_max_dims;
	ds_rank = H5Sget_simple_extent_ndims(dataspace);
	if (dims != NULL) {
		*dims = new hsize_t[ds_rank];
		call_dims = *dims;
	} else {
		call_dims = NULL;
	}
	if (maxdims != NULL) {
		*maxdims = new hsize_t[ds_rank];
		call_max_dims = *maxdims;
	} else {
		call_max_dims = NULL;
	}
	H5Sget_simple_extent_dims(dataspace, call_dims, call_max_dims);
	return ds_rank;
}

bool validate_dataset_shape(hid_t src_dataset, hid_t dest_dataset, size_t extension_dim) {
	/* take two datasets and validate that the dimensionality and type
	 * of the two datasets are the same */
	hid_t src_datatype = H5Dget_type(src_dataset);
	hid_t src_dataspace = H5Dget_space(src_dataset);
	hid_t dest_datatype = H5Dget_type(dest_dataset);
	hid_t dest_dataspace = H5Dget_space(dest_dataset);
	size_t src_rank, dest_rank;
	bool sizes_match = true;
	hsize_t *src_dims = NULL;
	hsize_t *src_maxdims = NULL;
	hsize_t *dest_dims = NULL;
	hsize_t *dest_maxdims = NULL;
	src_rank = get_dimensions(src_dataspace, &src_dims, &src_maxdims);
	dest_rank = get_dimensions(dest_dataspace, &dest_dims, &dest_maxdims);
	if (!H5Tequal (src_datatype, dest_datatype)) {
		sizes_match = false;
		goto validate_dataspace_shape_cleanup;
	}
	if (src_rank != dest_rank) {
		sizes_match = false;
		goto validate_dataspace_shape_cleanup;
	}
	for (size_t i = 0; i < src_rank; i ++) {
		/* skip the dimension that the dataset is extended into */
		if ( i == extension_dim ) continue;
		if (src_dims[i] != dest_dims[i]) {
			sizes_match = false;
			goto validate_dataspace_shape_cleanup;
		}
	}
validate_dataspace_shape_cleanup:
	delete[] src_dims;
	delete[] dest_dims;
	delete[] src_maxdims;
	delete[] dest_maxdims;
	return sizes_match;
}

size_t transfer_data(hid_t src_dataset, hid_t dest_dataset, size_t extension_dim) {
	/* get the data contained in the source dataset and append it to the 
	 * dest dataset. Extend the dest dataset as needed after checking that that is
	 * possible firs
	 *
	 * It is assumed that the data is of equal rank and dimensionality.
	 * The data is extended along the extension_dim axis
	 */

	hid_t src_dataspace = H5Dget_space(src_dataset);
	hid_t src_datatype = H5Dget_type(src_dataset);
	hsize_t *src_dims = NULL;
	hsize_t *src_maxdims = NULL;
	/* reserve space in main memmory to store the src_data temporarily */
	size_t src_rank = get_dimensions(src_dataspace, &src_dims, &src_maxdims);
	size_t appended_rows = src_dims[0];
	hsize_t src_total_element_count = 1;
	for (int i = 0; i < src_rank; i ++) {
		src_total_element_count *= src_dims[i];
	}
	void *in_mem_buffer = malloc(H5Tget_size(src_datatype) * src_total_element_count);
	if (in_mem_buffer == NULL) {
		std::cout << "Could not allocate the memmory necessary to hold the data of a"
			<< " source file" << std::endl;
		free(src_dims);
		free(src_maxdims);
		exit(EXIT_FAILURE);
	}
	/* extend the dataspace of the destination dataset */
	hid_t dest_dataspace = H5Dget_space(dest_dataset);
	hsize_t *dest_dims;
	hsize_t *dest_maxdims;
	size_t dest_rank = get_dimensions(dest_dataspace, &dest_dims, &dest_maxdims);
	if (extension_dim >= dest_rank) {
		std::cout << "The extension dimension of the dataset that is to be merged is"
			<< " larger than the dimensionality of the dataset" << std::endl;
		exit(EXIT_FAILURE);
	}
	dest_dims[extension_dim] += src_dims[extension_dim];
	H5Dextend(dest_dataset, dest_dims);
	H5Sclose(dest_dataspace);
	dest_dataspace = H5Dget_space(dest_dataset);
	/* calculate the starting point of the hyperslab in the extended dataspace */
	/* the size of the hyperslab is the src_dims */
	dest_dims[extension_dim] -= src_dims[extension_dim];
	for (size_t i = 0; i < dest_rank; i ++) {
		if ( i != extension_dim ) dest_dims[i] = 0;
	}
	H5Sselect_hyperslab(dest_dataspace, H5S_SELECT_SET, dest_dims, NULL, src_dims, NULL);
	H5Dread(src_dataset, src_datatype, src_dataspace, src_dataspace, H5P_DEFAULT, in_mem_buffer);
	H5Dwrite(dest_dataset, src_datatype, src_dataspace, dest_dataspace, H5P_DEFAULT, in_mem_buffer);
	H5Tclose(src_datatype);
	H5Sclose(src_dataspace);
	H5Sclose(dest_dataspace);
	delete[] src_dims;
	delete[] src_maxdims;
	free(in_mem_buffer);
	delete[] dest_dims;
	delete[] dest_maxdims;
	return appended_rows;
}

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
	if (status != 0) std::cout
		<< "create_utf8_attribute error writing attribute"
		<< status
		<< std::endl;
	status = H5Aclose(attribute_id);
	if (status != 0)
		std::cout
		<< "create_utf8_attribute error closing attribute"
		<< status
		<< std::endl;
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
	if (status != 0)
		std::cout << "create_empty_utf8_attribute error closing attribute"
		<< status
		<< std::endl;
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

std::vector<std::string> get_columns_in_block(hid_t group_id, int block_id) {
	/* get the columns in the block indicated by the block id */
	std::stringstream block_name;
	block_name << "block" << block_id << "_items";
	hid_t block_items = H5Dopen(group_id, block_name.str().c_str(), H5P_DEFAULT);
	if (block_items == H5I_INVALID_HID) {
		std::cout << block_name.str() << " does not exist in file, exiting";
		exit(EXIT_FAILURE);
	}
	hid_t block_item_type = H5Dget_type(block_items);
	if (H5Tget_class(block_item_type) != H5T_STRING) {
		std::cout << "The type of the item datatype is not STRING aborting." << std::endl;
		exit(EXIT_FAILURE);
	}
	hsize_t block_item_str_size = H5Tget_size(block_item_type);
	hsize_t *bi_dims = NULL;
	hsize_t *bi_max_dims = NULL;
	hid_t block_item_space = H5Dget_space(block_items);
	size_t bi_rank = get_dimensions(block_item_space, &bi_dims, &bi_max_dims);
	if (bi_rank != 1) {
		std::cout << "the block items has to be a 1D array" << std::endl;
		exit(EXIT_FAILURE);
	}
	hid_t item_mem_space = H5Screate_simple(1, bi_dims, NULL);
	char *buffer = new char[bi_dims[0] * block_item_str_size];
	H5Dread(block_items, block_item_type, item_mem_space, block_item_space, H5P_DEFAULT, buffer);
	std::vector<std::string> columns;
	for (size_t i = 0; i < bi_dims[0]; i++){
		columns.push_back(buffer + i * block_item_str_size);
	}
	H5Tclose(block_item_type);
	H5Sclose(block_item_space);
	H5Sclose(item_mem_space);
	H5Dclose(block_items);
	delete[] buffer;
	delete[] bi_dims;
	delete[] bi_max_dims;
	return columns;
}

hid_t get_block_dataset(hid_t group_id, int block_number) {
	std::stringstream block_values_name;
	block_values_name << "block" << block_number << "_values";
	hid_t block_values = H5Dopen(group_id, block_values_name.str().c_str(), H5P_DEFAULT);
	if ( block_values == H5I_INVALID_HID) {
		std::cout << "Error no " << block_values_name.str() << "in group" << std::endl;
		exit(EXIT_FAILURE);
	}
	return block_values;
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
	if (status != 0) std::cout << "error extending axis0" << status << std::endl;
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

void extend_axis1(hid_t axis1, hsize_t new_min_size) {
	hsize_t *ax_dim, *ax_maxdim;
	hid_t ax_type = 0;
	hid_t ax_space = 0;
	hid_t mem_space = 0;
	hsize_t delta_entries;
	int *buffer = NULL;
	ax_space = H5Dget_space(axis1);
	hsize_t ax_rank = get_dimensions(ax_space, &ax_dim, &ax_maxdim);
	if (ax_rank != 1) {
		std::cout << "An axis has more than one dimension, aborting" << std::endl;
		exit(EXIT_FAILURE);
	}

	/* check if we need to extend and are able to */
	if ( new_min_size <= ax_dim[0] ) {
		goto extend_axis_cleanup;
	}
	if ( ax_maxdim[0] != H5S_UNLIMITED ) {
		if ( new_min_size > ax_maxdim[0] ) {
			goto extend_axis_cleanup;
		}
	}

	/* extend the axis to the new size and select the hyperslab corresponding to the new elements*/
	delta_entries = new_min_size - ax_dim[0];
	H5Dextend(axis1, &new_min_size);
	ax_type = H5Dget_type(axis1);
	ax_space = H5Dget_space(axis1);
	H5Sselect_hyperslab(ax_space, H5S_SELECT_SET, ax_dim, NULL, &delta_entries, NULL);
	
	/* create and initialize the buffer holding the elements to be added onto the axis1 */
	buffer = (int *)malloc(delta_entries * sizeof(int));
	for (int i = ax_dim[0]; i < new_min_size; i ++) {
		buffer[i-ax_dim[0]] = i;
	}
	mem_space = H5Screate_simple(1, &delta_entries, NULL);
	H5Dwrite(axis1, ax_type, mem_space, ax_space, H5P_DEFAULT, buffer);
	H5Sclose(mem_space);
	H5Sclose(ax_space);
	H5Tclose(ax_type);
	free(buffer);
extend_axis_cleanup:
	delete[] ax_dim;
	delete[] ax_maxdim;
	return;
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

void append_file(hid_t dest_file, std::string group_name, std::string filename) {

	/* open the appropriate datasets from the output file */
	hid_t out_group = H5Gopen(dest_file, group_name.c_str(), H5P_DEFAULT);
	hid_t out_axis1 = H5Dopen(out_group, "axis1", H5P_DEFAULT);
	if (out_axis1 == H5I_INVALID_HID) {
		throw std::runtime_error("opening axis1 failed");
	}
	hsize_t *out_axis1_dim;
	hid_t axis1_space = H5Dget_space(out_axis1);
	size_t out_axis1_rank = get_dimensions(axis1_space, &out_axis1_dim, NULL);
	H5Sclose(axis1_space);
	if (out_axis1_rank != 1) {
		std::stringstream error_msg;
		error_msg << "Axis rank should be 1, dimension is " << out_axis1_rank;
		throw std::runtime_error(error_msg.str());
	}
	if (out_group == H5I_INVALID_HID) {
		throw std::runtime_error("Could not open group " + group_name + " in output file");
	}
	long out_block_count = get_block_count(out_group);
	std::vector<std::vector<std::string>> out_block_columns;
	std::vector<hid_t> out_block_values;
	for (size_t i = 0; i < out_block_count; i ++) {
		out_block_columns.push_back(get_columns_in_block(out_group, i));
		out_block_values.push_back(get_block_dataset(out_group, i));
	}
	
	/* open input file */
	hid_t in_file = H5Fopen(filename.c_str(), H5F_ACC_RDONLY, H5P_DEFAULT);
	if (in_file == H5I_INVALID_HID) {
		throw std::runtime_error("Could not open input file: " + filename);
	}
	hid_t in_group = H5Gopen(in_file, group_name.c_str(), H5P_DEFAULT);
	if (in_group == H5I_INVALID_HID) {
		throw std::runtime_error("Could not open group " + group_name + " in input file: " + filename);
	}
	/* get the blocks from the input file */
	std::vector<std::vector<std::string>> in_block_columns;
	std::vector<hid_t> in_block_values;
	long in_block_count = get_block_count(in_group);
	if (in_block_count != out_block_count) {
		std::stringstream error_message;
		error_message << "Block counts don't match; count of input file" << in_block_count
			<< "; count of output file: " << out_block_count;
		throw std::runtime_error(error_message.str());
	}
	for (size_t i = 0; i < in_block_count; i ++) {
		in_block_columns.push_back(get_columns_in_block(in_group, i));
		in_block_values.push_back(get_block_dataset(in_group, i));
	}
	for (size_t i = 0; i < in_block_count; i ++) {
		if (out_block_columns[i].size() != in_block_columns[i].size()) {
			std::stringstream error_message;
			error_message << "The columns in block " << i << " in file "
				<< filename << " don't match the columns in the output file";
			throw std::runtime_error(error_message.str());
		}
		for (size_t j = 0; j < in_block_columns[i].size(); j ++) {
			if (in_block_columns[i][j] != out_block_columns[i][j]) {
				std::stringstream error_message;
				error_message << "column " << j << " in block " << i
					<< " of file " << filename << ": " << in_block_columns[i][j]
					<< ", expected " << out_block_columns[i][j];
				throw std::runtime_error(error_message.str());
			}
		}
		bool datasets_match = validate_dataset_shape(in_block_values[i], out_block_values[i], 0);
		if (!datasets_match) {
			std::stringstream error_message;
			error_message << "Dimensionality does not fit between input and output of block "
				<< i << " for input file: " << filename;
			throw std::runtime_error(error_message.str());
		}
		size_t added_rows = transfer_data(in_block_values[i], out_block_values[i], 0);
		extend_axis1(out_axis1, out_axis1_dim[0] + added_rows);
	}
	delete[] out_axis1_dim;
	H5Gclose(in_group);
	H5Gclose(out_group);
	H5Fclose(in_file);
	for (size_t i = 0; i < out_block_values.size(); i ++) {
		H5Dclose(out_block_values[i]);
	}
	for (size_t i = 0; i < in_block_values.size(); i ++) {
		H5Dclose(in_block_values[i]);
	}
}

hid_t create_merge_output_file(std::string output_filename, std::string group_name, std::string input_filename) {
	/* create the basic structure for the output file */
	hid_t out_file_id = H5Fcreate(output_filename.c_str(), H5F_ACC_TRUNC, H5P_DEFAULT, H5P_DEFAULT);
	hid_t out_group_id = set_up_file(out_file_id, group_name.c_str());
	hid_t out_axis0, out_axis1;
	create_axes(out_group_id, &out_axis0, &out_axis1);
	hid_t in_file = H5Fopen(input_filename.c_str(), H5F_ACC_RDONLY, H5P_DEFAULT);
	hid_t in_group = H5Gopen(in_file, "data", H5P_DEFAULT);
	long block_count = get_block_count(in_group);
	/* for every block in the first input file create the block in the output file and copy the data over */
	for ( size_t i = 0; i < block_count; i ++) {
		std::vector<std::string> in_column_blocks = get_columns_in_block(in_group, i);
		hid_t in_block_dataset = get_block_dataset(in_group, i);
		hid_t in_block_data_type = H5Dget_type(in_block_dataset);
		hid_t in_block_dataspace = H5Dget_space(in_block_dataset);
		hsize_t *in_block_dim;
		size_t in_block_rank = get_dimensions(in_block_dataspace, &(in_block_dim), NULL);
		std::cout << "block_rank: " << in_block_rank << " block_dim: " << in_block_dim << std::endl;
		hid_t out_block_datasets = add_block(out_group_id, in_block_data_type, out_axis0, in_column_blocks);
		hid_t out_block_dataspace = H5Dget_space(out_block_datasets);
		hsize_t element_count = 1;
		for (int j = 0; j < in_block_rank; j ++) {
			element_count *= in_block_dim[j];
		}
		void *buffer = malloc(element_count * H5Tget_size(in_block_data_type));
		H5Dread(in_block_dataset, in_block_data_type, in_block_dataspace, in_block_dataspace, H5P_DEFAULT, buffer);
		write_to_block(out_block_datasets, out_axis1, in_block_dim[0], buffer);
		H5Dclose(in_block_dataset);
		H5Sclose(in_block_dataspace);
		H5Tclose(in_block_data_type);
		H5Dclose(out_block_datasets);
		H5Sclose(out_block_dataspace);
		free(buffer);
	}
	H5Dclose(out_axis1);
	H5Dclose(out_axis0);
	H5Gclose(out_group_id);
	H5Fclose(in_file);
	H5Gclose(in_group);
	return out_file_id;
}
