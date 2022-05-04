#ifndef HDF_UTILS_H_
#define HDF_UTILS_H_
#include <hdf5.h>
#include "../build/roc_param_description.hpp"
#include <iostream>
#include <sstream>
#include <string>
#include <vector>
#include <stdlib.h>

/* basic routines to simplify the construction of the internal hdf structur */
void create_utf8_attribute(hid_t root_id, std::string name,
                             std::string value);
void create_empty_utf8_attribute(hid_t root_id, std::string name);

hid_t create_dataset(hid_t root_id, std::string name, const hid_t datatype,
                     const hsize_t drank, const hsize_t *dimensions,
                     const hsize_t *maxdims, const hsize_t *chunk_dims,
                     unsigned int deflate);
template <typename T>
herr_t create_numeric_attribute(hid_t root_id, std::string name, hid_t datatype, const T *data) {
  herr_t status;
  hid_t attribute_space_id;
  hid_t attribute_id;
  attribute_space_id = H5Screate(H5S_SCALAR);
  attribute_id = H5Acreate(root_id, name.c_str(), datatype, attribute_space_id,
                           H5P_DEFAULT, H5P_DEFAULT);
  status = H5Awrite(attribute_id, datatype, (void *)data);
  if (status != 0)
    std::cout << status << std::endl;
  status = H5Aclose(attribute_id);
  if (status != 0)
    std::cout << status << std::endl;
  status = H5Sclose(attribute_space_id);
  return status;
}

/* helper functions for working with hdf5 strings */
std::vector<char> make_h5_compat_string(std::vector<std::string> strings,
                                        size_t hdf_string_size);

/* routines to work with datasets */
size_t get_dimensions(hid_t dataspace, hsize_t **dims, hsize_t **maxdims);
bool validate_dataset_shape(hid_t src_dataset, hid_t dest_dataset, size_t extension_dim);
size_t append_data(hid_t src_dataset, hid_t dest_dataset, size_t extension_dim);

/* routines to build the pandas like structure of a file */
void create_block_items(hid_t group_id, size_t block_number, std::vector<std::string> block_columns);
hid_t create_block_dataset(hid_t group_id, hid_t value_datatype, size_t block_number, size_t chunk_rows, size_t column_count);
hid_t add_block(hid_t group_id, hid_t value_datatype, std::vector<std::string> block_columns);
hid_t set_up_file(hid_t file_id, std::string group_name);
void create_axes(hid_t root_id, hid_t *axis0_id, hid_t *axis1_id);
void extend_axis0(hid_t axis, std::vector<std::string> block_columns);
void extend_axis1(hid_t axis, size_t new_min_size);
std::vector<std::string> get_columns_in_block(hid_t group_id, int block_id);
hid_t get_block_dataset(hid_t group, int block_id);
long get_block_count(hid_t group_id);
void write_to_block(hid_t ds_block_id, hid_t axis0_id, size_t rows, void *data);

/* more expansive pandas routines */
void append_file(hid_t dest_file, std::string group_name, std::string filename);
hid_t create_merge_output_file(std::string output_filename, std::string group_name, std::string input_filename);

/* pytables functions */
hid_t create_compound_datatype_form_columns(std::vector<std::string> data_columns, std::vector<std::string> config_columns);
hid_t create_pytables_file(std::string filename);
hid_t create_pytables_group(hid_t parent, std::string name, std::string description);
hid_t create_pytables_table(hid_t parent, std::string name, hid_t datatype, hsize_t chunk_rows);

#endif
