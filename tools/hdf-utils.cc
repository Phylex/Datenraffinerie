/**
 * @file hdf-utils.cc
 * utility functions to create the hdf structures to store the data/config in
 */
#include "include/hdf-utils.h"
#include "include/exceptions.h"
#include "include/root-tools.h"
#include <H5Dpublic.h>
#include <H5Ppublic.h>
#include <H5Spublic.h>
#include <string.h>

/**
 * Create an attribute with a UTF-8 string as content attached to the node
 * referenced with 'root_id'
 * @param[in] root_id
 * @param[in] name
 * @param[in] value
 */
void create_utf8_attribute(hid_t root_id, std::string name, std::string value) {
	hid_t attribute_space_id;
	hid_t datatype_id;
	hid_t attribute_id;
	herr_t status;

	// create attribute ID
	attribute_space_id = H5Screate(H5S_SCALAR);
	datatype_id = H5Tcopy(H5T_C_S1);
	H5Tset_cset(datatype_id, H5T_CSET_UTF8);
	if (value.size() > 0) {
		H5Tset_size(datatype_id, value.size());
	}
	
	// create actual attribute
	attribute_id = H5Acreate(root_id, name.c_str(),
							 datatype_id, attribute_space_id,
							 H5P_DEFAULT, H5P_DEFAULT
							);
	if (value.size() > 0) {
		H5Awrite(attribute_id, datatype_id, value.c_str());
	}
	H5Aclose(attribute_id);
	H5Sclose(attribute_space_id);
	H5Tclose(datatype_id);
}

bool compare_compound_data_types(hid_t t1, hid_t t2) {
	int m1 = H5Tget_nmembers(t1);
	int m2 = H5Tget_nmembers(t2);
	if (m1 != m2) return false;
	for (int i = 0; i < m1; i ++) {
		char *n1 = H5Tget_member_name(t1, i);
		char *n2 = H5Tget_member_name(t2, i);
		if (strcmp(n1, n2)) return false;
		hid_t st1 = H5Tget_member_type(t1, i);
		hid_t st2 = H5Tget_member_type(t2, i);
		if (H5Tget_class(st1) != H5Tget_class(st2)) return false;
		if (H5Tget_class(st1) == H5T_COMPOUND) {
			if (!compare_compound_data_types(st1, st2)) return false;
		}
		if (H5Tget_size(t1) != H5Tget_size(t2)) return false;
		H5Tclose(st1);
		H5Tclose(st2);
		free(n1);
		free(n2);
	}
	return true;
}


void create_empty_utf8_attribute(hid_t root_id, std::string attr_name) {
	create_utf8_attribute(root_id, attr_name, "");
}

hid_t create_compund_datatype(std::vector<std::string> column_names, std::vector<hid_t> column_types) {
	hsize_t total_size = 0;
	std::vector<hsize_t> offsets;
	for (hid_t type: column_types) {
		offsets.push_back(total_size);
		total_size += H5Tget_size(type);
	}
	hid_t compound_datatype = H5Tcreate(H5T_COMPOUND, total_size);
	for (size_t column_idx = 0; column_idx < column_names.size(); column_idx++) {
		H5Tinsert(compound_datatype, column_names[column_idx].c_str(), offsets[column_idx], column_types[column_idx]);
	}
	return compound_datatype;
}

hid_t get_pytable_type(std::string filepath, std::string group_name, std::string table_name) {
	hid_t hdf_file = H5Fopen(filepath.c_str(), H5P_DEFAULT, H5P_DEFAULT);
	hid_t group = H5Gopen(hdf_file, group_name.c_str(), H5P_DEFAULT);
	hid_t table = H5Dopen(group, table_name.c_str(), H5P_DEFAULT);
	return H5Dget_type(table);
}

/** 
 * generate the datatype that contains both the relevant measurement and configuration information
 * given the column names of the 
 **/
hid_t create_compound_datatype_form_columns(std::vector<std::string> data_columns, std::vector<std::string> config_columns, bool event_mode) {
	std::vector<std::string> names;
	std::vector<hid_t> dtypes;
	hgcroc_data data;
	hgcroc_summary_data summary;
	for (std::string column: data_columns) {
		hid_t elem;
		if (event_mode) {
			elem = data.get_hdf_type(column.c_str());
		} else {
			elem = summary.get_hdf_type(column.c_str());
		}
		dtypes.push_back(elem);
		names.push_back(column);
	} 
	for (std::string column: config_columns) {
		hid_t elem = column_type[column];
		dtypes.push_back(elem);
		names.push_back(column);
	} 
	return create_compund_datatype(names, dtypes);
}

hid_t create_pytables_file(std::string filename) {
	hid_t hdf_file = H5Fcreate(filename.c_str(), H5F_ACC_TRUNC, H5P_DEFAULT, H5P_DEFAULT);
	create_utf8_attribute(hdf_file, "CLASS", "GROUP");
	create_utf8_attribute(hdf_file, "PYTABLES_FORMAT_VERSION", "2.1");
	create_utf8_attribute(hdf_file, "VERSION", "1.0");
	create_utf8_attribute(hdf_file, "TITLE", filename.c_str());
	return hdf_file;
}

hid_t create_pytables_group(hid_t parent, std::string name, std::string description) {
	hid_t group = H5Gcreate2(parent, name.c_str(), H5P_DEFAULT, H5P_DEFAULT, H5P_DEFAULT);
	create_utf8_attribute(group, "CLASS", "GROUP");
	create_utf8_attribute(group, "VERSION", "1.0");
	create_utf8_attribute(group, "TITLE", description.c_str());
	return group;
}

hid_t create_pytables_table(hid_t parent, std::string name, hid_t datatype, hsize_t chunk_rows, unsigned int deflate) {
	hsize_t maxdims[] = {H5S_UNLIMITED};
	hsize_t chunk_dims[] = {chunk_rows};
	hsize_t start_dims[] = {0};
	const hsize_t drank = 1;
	hid_t dataspace = H5Screate_simple(1, start_dims, maxdims);
	hid_t properties = H5Pcreate(H5P_DATASET_CREATE);
	if (chunk_rows > 0) {
		H5Pset_chunk(properties, drank, chunk_dims);
		H5Pset_deflate(properties, deflate);
	}
	hid_t dataset = H5Dcreate(parent, name.c_str(), datatype, dataspace, H5P_DEFAULT,
							  properties, H5P_DEFAULT);
	H5Pclose(properties);
	H5Sclose(dataspace);
	create_utf8_attribute(dataset, "CLASS", "TABLE");
	create_utf8_attribute(dataset, "TITLE", name.c_str());
	create_utf8_attribute(dataset, "VERSION", "2.7");
	int nmembers = H5Tget_nmembers(datatype);
	for (int i=0; i<nmembers; i++) {
		std::stringstream name;
		name << "FIELD_" << i << "_NAME";
		create_utf8_attribute(dataset, name.str().c_str(), H5Tget_member_name(datatype, i));
		name.str("");
		name << "FIELD_" << i << "_FILL";
		short fill_val = 0;
		create_numeric_attribute<short>(dataset, name.str().c_str(), H5Tget_member_type(datatype, i), &fill_val);
	}
	return dataset;
}

void write_buffer_to_pytable(hid_t table, hid_t buffer_datatype, hsize_t buffer_size, void* buffer){
	hid_t buffer_dspace = H5Screate_simple(1, &buffer_size, &buffer_size);
	hid_t table_dspace = H5Dget_space(table);
	hsize_t *dims;
	hsize_t *maxdims;
	hsize_t rank = get_dimensions(table_dspace, &dims, &maxdims);
	if (rank != 1) {
		std::cout << "Rank of table is not 1" << std::endl;
		exit(EXIT_FAILURE);
	}
	H5Sclose(table_dspace);
	dims[0] += buffer_size; 
	H5Dextend(table, dims);
	table_dspace = H5Dget_space(table);
	rank = get_dimensions(table_dspace, &dims, &maxdims);
	hsize_t new_data_offset = *dims - buffer_size;
	H5Sselect_hyperslab(table_dspace, H5S_SELECT_SET, &new_data_offset, NULL, &buffer_size, NULL);
	H5Dwrite(table, buffer_datatype, buffer_dspace, table_dspace, H5P_DEFAULT, buffer);
	free(dims);
	free(maxdims);
	H5Sclose(table_dspace);
	H5Sclose(buffer_dspace);
}

void merge_tables(hid_t merge_file, hid_t input_file, std::string group_name, std::string table_name, hsize_t block_length) {
	/* open the groups and tables in the output file */
	hid_t out_group = H5Gopen(merge_file, group_name.c_str(), H5P_DEFAULT);
	if (out_group == H5I_INVALID_HID) {
		throw std::runtime_error("Could not open group " + group_name + " in output file");
	}
	hid_t out_table = H5Dopen(out_group, table_name.c_str(), H5P_DEFAULT);
	if (out_table == H5I_INVALID_HID) {
		throw std::runtime_error("Could not open group " + table_name + " in output file");
	}
	hid_t out_dspace = H5Dget_space(out_table);
	hsize_t *out_dspace_dim;
	size_t out_trank = get_dimensions(out_dspace, &out_dspace_dim, NULL);
	H5Sclose(out_dspace);
	if (out_trank != 1) {
		std::stringstream error_msg;
		error_msg << "Table dimension should be 1, dimension is " << out_trank;
		throw std::runtime_error(error_msg.str());
	}
	hid_t merge_type = H5Dget_type(out_table);
	
	/* open input file */
	hid_t in_group = H5Gopen(input_file, group_name.c_str(), H5P_DEFAULT);
	if (in_group == H5I_INVALID_HID) {
		throw std::runtime_error("Could not open group " + group_name + " in input file");
	}
	hid_t in_table = H5Dopen(in_group, table_name.c_str(), H5P_DEFAULT);
	if (in_group == H5I_INVALID_HID) {
		throw std::runtime_error("Could not open table " + table_name + " in input file");
	}
	hid_t in_dspace = H5Dget_space(in_table);
	hsize_t *in_dspace_dim;
	size_t in_dspace_rank = get_dimensions(in_dspace, &in_dspace_dim, NULL);
	H5Sclose(in_dspace);
	if (in_dspace_rank != 1) {
		std::stringstream error_msg;
		error_msg << "Table dimension should be 1, dimension is " << in_dspace_rank;
		throw std::runtime_error(error_msg.str());
	}
	hid_t in_type = H5Dget_type(in_table);
	if (!compare_compound_data_types(merge_type, in_type)) {
		throw std::runtime_error("Types do not match/are incompatible");
	}

	/* after having done all the loads and checks, actually copy the data */
	void *buffer = malloc(block_length * H5Tget_size(in_type));
	hid_t memspace = H5Screate_simple(1, &block_length, &block_length);
	hsize_t block_count = in_dspace_dim[0] / block_length;
	for (hsize_t i = 0; i<block_count; i++) {
		hid_t block_dspace = H5Dget_space(in_table);
		hsize_t start = block_length * i;
		H5Sselect_hyperslab(block_dspace, H5S_SELECT_SET, &start, NULL, &block_length, NULL);
	  H5Dread(in_table, in_type, memspace, block_dspace, H5P_DEFAULT, buffer);
		H5Sclose(block_dspace);
    write_buffer_to_pytable(out_table, in_type, block_length, buffer);
	}
	H5Sclose(memspace);
	hid_t block_dspace = H5Dget_space(in_table);
	hsize_t start = block_length * block_count;
	hsize_t last_block_length = in_dspace_dim[0] % block_length; 
	memspace = H5Screate_simple(1, &last_block_length, &last_block_length);
	if (last_block_length != 0) {
		H5Sselect_hyperslab(block_dspace, H5S_SELECT_SET, &start, NULL, &last_block_length, NULL);
		H5Dread(in_table, in_type, memspace, block_dspace, H5P_DEFAULT, buffer);
		H5Sclose(block_dspace);
  	write_buffer_to_pytable(out_table, in_type, last_block_length, buffer);
	}
	/* clean up */ 
	free(buffer);
	free(in_dspace_dim);
	free(out_dspace_dim);
	H5Sclose(memspace);
	H5Tclose(in_type);
	H5Tclose(merge_type);
	H5Gclose(out_group);
	H5Dclose(out_table);
	H5Gclose(in_group);
	H5Dclose(in_table);
}

hid_t create_dataset(hid_t root_id, std::string name, const hid_t datatype,
                     const hsize_t drank, const hsize_t *dimensions,
                     const hsize_t *maxdims, const hsize_t *chunk_dims,
                     unsigned int deflate) {
  hid_t dataspace = H5Screate_simple(drank, dimensions, maxdims);
  hid_t properties = H5Pcreate(H5P_DATASET_CREATE);
  if (chunk_dims != NULL) {
    H5Pset_chunk(properties, drank, chunk_dims);
    if (deflate > 0) {
      H5Pset_deflate(properties, deflate);
    }
  }
  hid_t dataset = H5Dcreate(root_id, name.c_str(), datatype, dataspace, H5P_DEFAULT,
                      properties, H5P_DEFAULT);
  H5Pclose(properties);
  H5Sclose(dataspace);
  return dataset;
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

size_t append_data(hid_t src_dataset, hid_t dest_dataset, size_t extension_dim) {
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

void create_block_items(hid_t group_id, size_t block_number, std::vector<std::string> block_columns) {
	hid_t datatype = H5Tcopy(H5T_C_S1);
	H5Tset_size(datatype, 50);
	H5Tset_cset(datatype, H5T_CSET_UTF8);
	hsize_t block_item_dim[] = {block_columns.size()};
	hid_t dataspace = H5Screate_simple(1, block_item_dim, NULL);
	std::stringstream block_item_name;
	block_item_name << "block" << block_number << "_items";
	hid_t block_items = H5Dcreate(group_id, block_item_name.str().c_str(), datatype,
								  dataspace, H5P_DEFAULT, H5P_DEFAULT, H5P_DEFAULT);
	std::vector<char> col_string = make_h5_compat_string(block_columns, 50);
	H5Dwrite(block_items, datatype, dataspace, dataspace, H5P_DEFAULT, col_string.data());
	H5Sclose(dataspace);
	H5Tclose(datatype);
	create_utf8_attribute(block_items, "CLASS", "ARRAY");
	create_utf8_attribute(block_items, "FLAVOUR", "numpy");
	create_empty_utf8_attribute(block_items, "TITLE");
	create_utf8_attribute(block_items, "VERSION", "2.4");
	create_utf8_attribute(block_items, "kind", "string");
	create_utf8_attribute(block_items, "name", "N.");
	long transposed = 1;
	create_numeric_attribute<long>(block_items, "transposed", H5T_STD_I64LE, &transposed);
	H5Dclose(block_items);
}

hid_t create_block_dataset(hid_t group_id, hid_t value_datatype, size_t block_number, size_t chunk_rows, size_t column_count) {
	std::stringstream block_val_name;
	block_val_name << "block" << block_number << "_values";
	const hsize_t val_rank = 2;
	hsize_t val_dim[] = {0, column_count};
	hsize_t max_dim[] = {H5S_UNLIMITED, column_count};
	hsize_t chunk_dim[] = {chunk_rows, column_count};
	hid_t val_dataset = create_dataset(group_id, block_val_name.str(), value_datatype, val_rank, val_dim, max_dim, chunk_dim, 3);
	create_utf8_attribute(val_dataset, "CLASS", "ARRAY");
	create_utf8_attribute(val_dataset, "FLAVOUR", "numpy");
	create_empty_utf8_attribute(val_dataset, "TITLE");
	create_utf8_attribute(val_dataset, "VERSION", "2.4");
	create_utf8_attribute(val_dataset, "kind", "string");
	create_utf8_attribute(val_dataset, "name", "N.");
	long transposed = 1;
	create_numeric_attribute<long>(val_dataset, "transposed", H5T_STD_I64LE, &transposed);
	return val_dataset;
}

hid_t add_block(hid_t group_id, hid_t value_datatype, std::vector<std::string> block_items) {
	/* get the number of blocks already in the group and create the attributes for the
	 * new block in the group */
	hid_t nblocks;
	long block_count;
	nblocks = H5Aopen(group_id, "nblocks", H5P_DEFAULT);
	H5Aread(nblocks, H5T_STD_I64LE, (void *)(&block_count));
	std::stringstream block_name;
	block_name << "block" << block_count << "_items_variety";
	block_count ++;
	H5Awrite(nblocks, H5T_STD_I64LE, &block_count);
	H5Aclose(nblocks);
	block_count --;
	create_utf8_attribute(group_id, block_name.str(), "regular");
	/* create the blockx_items dataset */
	create_block_items(group_id, block_count, block_items);
	/* extend the axis holding the column names */
	extend_axis0(group_id, block_items);
	/* create an empty extensible dataset for the block values */
	hid_t val_dataset = create_block_dataset(group_id, value_datatype, block_count, 10000, block_items.size());
	return val_dataset;
}

hid_t set_up_file(hid_t file_id, std::string group_name) {
	/* set file wide attributes */
	create_utf8_attribute(file_id, "CLASS", "GROUP");
	create_utf8_attribute(file_id, "PYTABLES_FORMAT_VERSION", "2.1");
	create_utf8_attribute(file_id, "VERSION", "1.0");
	create_empty_utf8_attribute(file_id, "TITLE");

	/* create the groud and the properties of the group */
	hid_t group_id = H5Gcreate2(file_id, group_name.c_str(), H5P_DEFAULT, H5P_DEFAULT, H5P_DEFAULT);
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

void create_axes(hid_t root_id, hid_t *axis0_id, hid_t *axis1_id) {
	/* set the parameters for the axis 0 */
	hsize_t ndims = 1;
	hsize_t dimensions[] = {0};
	hsize_t max_dimensions[] = {H5S_UNLIMITED};
	hsize_t chunk_dimensions[] = {5};
	int exdim = 0;
	long transposed = 1;

	/* create the actual axis in the dataset */
	create_utf8_attribute(root_id, "axis0_variety", "regular");
	hid_t datatype = H5Tcopy(H5T_C_S1);
	H5Tset_size(datatype, 50);
	*axis0_id = create_dataset(root_id, "axis0", datatype, ndims, dimensions, max_dimensions, chunk_dimensions, 0);
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
	dimensions[0] = 0;
	chunk_dimensions[0] = 200000;
	datatype = H5Tcopy(H5T_STD_I32LE);
	*axis1_id = create_dataset(root_id, "axis1", datatype, ndims, dimensions, max_dimensions, chunk_dimensions, 3);
	create_utf8_attribute(*axis1_id, "CLASS", "EARRAY");
	create_numeric_attribute<int>(*axis1_id, "EXTDIM", H5T_STD_I32LE, &exdim);
	create_empty_utf8_attribute(*axis1_id, "TITLE");
	create_utf8_attribute(*axis1_id, "VERSION", "1.1");
	create_utf8_attribute(*axis1_id, "kind", "string");
	create_utf8_attribute(*axis1_id, "name", "values");
	create_numeric_attribute<long>(*axis1_id, "transposed", H5T_STD_I64LE, &transposed);
}

void extend_axis0(hid_t group_id, std::vector<std::string> block_columns) {
	hid_t axis = H5Dopen(group_id, "axis0", H5P_DEFAULT);
	hid_t axis_type = H5Dget_type(axis);
	hid_t axis_space = H5Dget_space(axis);
	hsize_t *axis_dim;
	size_t axis_string_size = H5Tget_size(axis_type);
	size_t axis_rank = get_dimensions(axis_space, &axis_dim, NULL);
	if (axis_rank != 1) {
		delete[] axis_dim;
		H5Tclose(axis_type);
		H5Sclose(axis_space);
		H5Dclose(axis);
		throw std::runtime_error("Axis Rank is not 1");
	}

	/* extend the axis0 */
	axis_dim[0] += block_columns.size();
	H5Dextend(axis, axis_dim);
	/* reload ax space */
	H5Sclose(axis_space);
	axis_space = H5Dget_space(axis);

	/* copy the data from the vector of block_item names into the file */
	hsize_t start[] = {axis_dim[0] - block_columns.size()};
	hsize_t count[] = {block_columns.size()};
	H5Sselect_hyperslab(axis_space, H5S_SELECT_SET, start, NULL, count, NULL);
	hid_t mem_space = H5Screate_simple(1, count, NULL);
	std::vector<char> block_item_str = make_h5_compat_string(block_columns, axis_string_size);
	H5Dwrite(axis, axis_type, mem_space, axis_space, H5P_DEFAULT, block_item_str.data());
	delete[] axis_dim;
	H5Sclose(mem_space);
	H5Tclose(axis_type);
	H5Sclose(axis_space);
	H5Dclose(axis);
};

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
		H5Sclose(ax_space);
		delete[] ax_dim;
		delete[] ax_maxdim;
		throw std::runtime_error("An axis has more than one dimension, aborting");
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
	buffer = new int[delta_entries];
	for (int i = ax_dim[0]; i < new_min_size; i ++) {
		buffer[i-ax_dim[0]] = i;
	}
	mem_space = H5Screate_simple(1, &delta_entries, NULL);
	H5Dwrite(axis1, ax_type, mem_space, ax_space, H5P_DEFAULT, buffer);
	H5Sclose(mem_space);
	H5Tclose(ax_type);
	delete[] buffer;
extend_axis_cleanup:
	H5Sclose(ax_space);
	delete[] ax_dim;
	delete[] ax_maxdim;
	return;
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
	char *complete_buffer = new char[bi_dims[0] * block_item_str_size];
	char *col_buffer = new char[block_item_str_size + 1];
	H5Dread(block_items, block_item_type, item_mem_space, block_item_space, H5P_DEFAULT, complete_buffer);
	std::vector<std::string> columns;
	for (size_t i = 0; i < bi_dims[0]; i++){
		for (size_t j = 0; j < block_item_str_size; j++) {
			col_buffer[j] = complete_buffer[i * block_item_str_size + j];
		}
		col_buffer[block_item_str_size] = 0;
		columns.push_back(col_buffer);
	}
	H5Tclose(block_item_type);
	H5Sclose(block_item_space);
	H5Sclose(item_mem_space);
	H5Dclose(block_items);
	delete[] complete_buffer;
	delete[] bi_dims;
	delete[] bi_max_dims;
	return columns;
}

hid_t get_block_dataset(hid_t group_id, int block_number) {
	std::stringstream block_values_name;
	block_values_name << "block" << block_number << "_values";
	hid_t block_values = H5Dopen(group_id, block_values_name.str().c_str(), H5P_DEFAULT);
	if ( block_values == H5I_INVALID_HID) {
		std::stringstream error_message;
		error_message << "Could not open " << block_values_name.str();
		throw std::runtime_error(error_message.str());
	}
	return block_values;
}

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

/* write a number of rows to the block indicated by ds_block_id from data */
/* the caller must make sure that data is large enough to hold all the data indicated
 * by the number of columns of the block and the number of rows indicated */
void write_to_block(hid_t ds_block_id, hid_t axis1_id, size_t rows, void *data) {
	hid_t block_datatype = H5Dget_type(ds_block_id);
	
	/* get the dimensions of the block */
	hid_t block_dataspace = H5Dget_space(ds_block_id);
	hsize_t *ds_dims;
	hsize_t *max_ds_dims;
	size_t ds_rank = get_dimensions(block_dataspace, &ds_dims, &max_ds_dims);
	H5Sclose(block_dataspace);

	/* exit if there is no space in the dataframe */
	if (ds_dims[0] + rows > max_ds_dims[0]) {
		std::cout << "Adding rows to dataset extends beyond the maximal dimensions" << std::endl;
		delete[] ds_dims;
		delete[] max_ds_dims;
		H5Tclose(block_datatype);
		std::stringstream error_message;
		error_message << "Adding rows would lead to a dataset with " << ds_dims[0] + rows
			<< "but maximum dimension is: " << max_ds_dims[0];
		throw std::runtime_error(error_message.str());
	}
	delete[] max_ds_dims;

	/* initialize the size of the region in memmory */
	hsize_t *mem_ds_dims = new hsize_t[ds_rank];
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
		size_t added_rows = append_data(in_block_values[i], out_block_values[i], 0);
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
		hid_t out_block_datasets = add_block(out_group_id, in_block_data_type, in_column_blocks);
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
