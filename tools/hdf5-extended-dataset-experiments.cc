#include <stdio.h>
#include <malloc.h>
#include "hdf5.h"

#define FNAME "extended-dataset-experiment.h5"

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
	hsize_t max_dimensions[RANK] = {H5S_UNLIMITED, NCOL};
	
	/* initialize the datatype of the dataset */
	hid_t datatype = H5Tcopy(H5T_NATIVE_INT);
	status = H5Tset_order(datatype, H5T_ORDER_LE);
	
	/* initialize the dataspace of the dataset make the rows expandable */
	hid_t dataspace = H5Screate_simple(RANK, dimensions, max_dimensions);

	/* enable chunking in the creation properties */
	hsize_t chunk_dimensions[RANK] = {100, NCOL};
	hid_t creation_properties = H5Pcreate(H5P_DATASET_CREATE);
	status = H5Pset_chunk(creation_properties, RANK, chunk_dimensions);
	printf("Status of creation property chunk enable: %i", status);
	
	/* create the dataset currently using the default creation properties*/
	hid_t dataset = H5Dcreate(file, DSET_NAME, datatype, dataspace, H5P_DEFAULT, creation_properties, H5P_DEFAULT);
	
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

	/* extend the dataset */
	dimensions[0] = dimensions[0] + 200;
	status = H5Dextend(dataset, dimensions);
	printf("Status after extend dataset: %i\n", status);
	hsize_t changed_dimensions[RANK];
	status = H5Sget_simple_extent_dims(dataspace, changed_dimensions, NULL);
	printf("rank after extend dataset: %i\n", status);
	printf("Dimensions of the old dataspace after extension:\nRows: %lli\nColumns %lli\n", changed_dimensions[0], changed_dimensions[1]);
	H5Sclose(dataspace);
	dataspace = H5Dget_space(dataset);
	status = H5Sget_simple_extent_dims(dataspace, changed_dimensions, NULL);
	printf("Dimensions of the new dataspace after extension:\nRows: %lli\nColumns %lli\n", changed_dimensions[0], changed_dimensions[1]);


	/* clear the data in memmory */
	data = NULL;
	free(raw_data);
	raw_data = NULL;

	/* close dataset */
	H5Tclose(datatype);
	H5Dclose(dataset);
	/* close the file */
	H5Fclose(file);
}
