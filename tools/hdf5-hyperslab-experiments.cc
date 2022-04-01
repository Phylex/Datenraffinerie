#include <stdio.h>
#include <malloc.h>
#include "hdf5.h"

#define FNAME "test-hdf-routines.h5"

#define DSET_NAME "data"
#define RANK 2
#define NROW 100
#define NCOL 10

int main() {
	/* create an error variable to store possible errors in*/
	herr_t status;
	/* create an hdf5 file */
	hid_t file = H5Fcreate(FNAME, H5F_ACC_TRUNC, H5P_DEFAULT, H5P_DEFAULT);
	
	/* create a dataset with the corresponding dataspace and datatype */
	/* initialize the variable used to describe the dimensionality */
	hsize_t dimensions[RANK] = {NROW, NCOL};
	
	/* initialize the datatype of the dataset */
	hid_t datatype = H5Tcopy(H5T_NATIVE_INT);
	status = H5Tset_order(datatype, H5T_ORDER_LE);
	
	/* initialize the dataspace of the dataset */
	hid_t dataspace = H5Screate_simple(RANK, dimensions, NULL);
	
	/* create the dataset currently using the default creation properties*/
	hid_t dataset = H5Dcreate(file, DSET_NAME, datatype, dataspace, H5P_DEFAULT, H5P_DEFAULT, H5P_DEFAULT);
	
	/* write to all of the dataset */
	/* reserve the space needed for the data in memmory */
	void *raw_data = malloc(NROW * NCOL * sizeof(int));
	size_t raw_data_size = NROW * NCOL * sizeof(int);
	/* cast the pointer to the */
	int *data = (int *)raw_data;
	size_t data_size = raw_data_size / sizeof(int);
	for (size_t i = 0; i < NROW; i++) {
		for ( size_t j = 0; j < NCOL; j++) {
			data[i*NCOL + j] = i * 10 + j;
		}
	}

	/* write the initial data to the dataset */
	H5Dwrite(dataset, datatype, H5S_ALL, H5S_ALL, H5P_DEFAULT, data);

	/* close the dataspace */
	H5Sclose(dataspace);

	/* clear the data in memmory */
	data = NULL;
	data_size = 0;
	free(raw_data);
	raw_data = NULL;
	raw_data_size = 0;

	/* get the file dataspace and print information about it */
	hid_t file_dataspace = H5Dget_space(dataset);
	hsize_t dsp_rank = H5Sget_simple_extent_ndims(file_dataspace);
	hsize_t *dims = (hsize_t *)malloc(dsp_rank * sizeof(hsize_t));
	dsp_rank = H5Sget_simple_extent_dims(file_dataspace, dims, NULL);
	printf("Dataspace rank: %lli\nRows: %lli\nColumns: %lli\n", dsp_rank, dims[0], dims[1]);
	free(dims);
	dims = NULL;
	
	/* select a hyperslab from the file dataspace */
	hsize_t slice_start[2];
	hsize_t slice_stride[2];
	hsize_t slice_block[2];
	hsize_t slice_count[2];
	slice_start[0] = 0; slice_start[1] = 0;
	slice_stride[0] = 10; slice_stride[1] = 3;
	slice_block[0] = 5; slice_block[1] = 2;
	slice_count[0] = 3; slice_count[1] = 2;
	hsize_t element_count;
	element_count = slice_block[0] * slice_block[1] * slice_count[0] * slice_count[1];
	status = H5Sselect_hyperslab(file_dataspace, H5S_SELECT_SET, slice_start, slice_stride, slice_count, slice_block);
	printf("Status from the \'select hyperslab\' call: %i\n", status);
	printf("Number of elements: %lli\n", element_count);

	/* create a dataspace in memmory and the associated buffer */
	int *buffer = (int *)malloc(element_count * sizeof(int));
	hid_t memspace = H5Screate_simple(1, &element_count, NULL);

	/* read the data from the file into memmory */
	/* note that the memmory space is the targer of the read */
	H5Dread(dataset, datatype, memspace, file_dataspace, H5P_DEFAULT, buffer);

	/* print the contents of the buffer */
	printf("Contents of the buffer\n");
	printf("[");
	for (size_t i = 0; i < element_count; i ++) {
		printf("%i", buffer[i]);
		if (i < element_count - 1)
			printf(", ");
	}
	printf("]");

	/* write new content into the buffer */
	for (size_t i = 0; i < element_count; i ++) {
		buffer[i] = 1000;
	}

	/* write the new buffer content into the hyperslab in the file */
	H5Dwrite(dataset, datatype, memspace, file_dataspace, H5P_DEFAULT, buffer);

	/* release the memmory of the buffer */
	free(buffer);
	buffer = NULL;

	/* close dataset */
	H5Sclose(file_dataspace);
	H5Sclose(memspace);
	H5Tclose(datatype);
	H5Dclose(dataset);
	/* close the file */
	H5Fclose(file);
}
