#ifndef HDF_UTILS_H_
#define HDF_UTILS_H_
#include "hdf5.h"
#include <iostream>
#include <sstream>
#include <string>
#include <vector>
#include <stdlib.h>

herr_t create_utf8_attribute(hid_t root_id, std::string name,
                             std::string value);
herr_t create_empty_utf8_attribute(hid_t root_id, std::string name);
void create_axes(hid_t root_id, hid_t *axis0_id, hid_t *axis1_id);
void extend_axis0(hid_t axis, std::vector<std::string> block_columns);
void extend_axis1(hid_t axis, size_t new_min_size);
hid_t set_up_file(hid_t file_id, std::string group_name);
hid_t add_block(hid_t group_id, hid_t datatype, hid_t axis0,
               std::vector<std::string> block_columns);
size_t get_dimensions(hid_t dataspace, hsize_t **dims, hsize_t **maxdims);
std::vector<std::string> get_columns_in_block(hid_t group_id, int block_id);
hid_t get_block_dataset(hid_t group, int block_id);
bool validate_dataset_shape(hid_t src_dataset, hid_t dest_dataset, size_t extension_dim);
void append_file(hid_t dest_file, std::string group_name, std::string filename);
size_t transfer_data(hid_t src_dataset, hid_t dest_dataset, size_t extension_dim);
void write_to_block(hid_t ds_block_id, hid_t axis0_id, size_t rows, void *data);
long get_block_count(hid_t group_id);
hid_t create_merge_output_file(std::string output_filename, std::string group_name, std::string input_filename);
void append_file(hid_t dest_file_id, std::string group, std::string src_file_name);
std::vector<char> make_h5_compat_string(std::vector<std::string> strings,
                                        size_t hdf_string_size);
template <typename T>
herr_t create_numeric_attribute(hid_t root_id, std::string name, hid_t datatype,
                                const T *data) {
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
template <typename T>
hid_t create_dataset(hid_t root_id, std::string name, const hid_t datatype,
                     const hsize_t drank, const hsize_t *dimensions,
                     const hsize_t *maxdims, const hsize_t *chunk_dims,
                     unsigned int deflate, std::vector<T> data) {
  herr_t status;
  hid_t dataspace;
  hid_t dataset;
  hid_t properties;
  dataspace = H5Screate_simple(drank, dimensions, maxdims);
  properties = H5Pcreate(H5P_DATASET_CREATE);
  if (chunk_dims != NULL) {
    status = H5Pset_chunk(properties, drank, chunk_dims);
    if (status != 0)
      std::cout << status << std::endl;
    if (deflate > 0) {
      status = H5Pset_deflate(properties, deflate);
      if (status != 0)
        std::cout << status << std::endl;
    }
  }
  dataset = H5Dcreate(root_id, name.c_str(), datatype, dataspace, H5P_DEFAULT,
                      properties, H5P_DEFAULT);
  if (data.size() > 0)
    status =
        H5Dwrite(dataset, datatype, H5S_ALL, H5S_ALL, H5P_DEFAULT, data.data());
  if (status != 0)
    std::cout << status << std::endl;
  status = H5Pclose(properties);
  if (status != 0)
    std::cout << status << std::endl;
  status = H5Sclose(dataspace);
  if (status != 0)
    std::cout << status << std::endl;
  return dataset;
}

#endif /* end of include guard: HDF_UTILS_H_ */
