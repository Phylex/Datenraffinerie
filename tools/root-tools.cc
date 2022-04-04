#include "include/root-tools.h"

TTree *openRootTree(std::string root_file_path, bool *event_mode) {
	/* open the ROOT file containing the measurement data */
	std::unique_ptr<TFile> Measurement(TFile::Open(root_file_path.c_str(), "READ"));
	/* make sure that the file can be opened by root */
	if ( !Measurement || Measurement->IsZombie() ) {
		std::cout << "Unable to open Root file: " << root_file_path << std::endl;
		exit(EXIT_FAILURE);
	}

	/* determine if we are running in event mode or in summary mode */
	/* and select the tree containing the data from the root file */
	bool event_mode = false;
	TTree *tree;
	TObject *data_dir = Measurement->Get("runsummary");
	if ( data_dir == NULL ) {
		event_mode = true;
		tree = (TTree *)Measurement->Get("unpacker_data/hgcroc");
	} else {
		tree = (TTree *)Measurement->Get("runsummary/summary");
	}
	return tree;
}

static std::vector<std::string> summary_data_columns = {
	"chip", "channel", "channeltype", "adc_median", "adc_iqr", "tot_median",
	"tot_iqr", "toa_median", "toa_iqr", "toa_mean", "tot_mean", "adc_mean",
	"adc_stdd", "toa_stdd", "tot_stdd", "tot_efficiency", "tot_efficiency_error",
	"toa_efficiency", "toa_efficiency_error" };

static std::vector<std::string> event_mode_data_columns = {
	"event", "chip", "half", "channel", "adc", "adcm", "toa",
	"tot", "totflag", "trigtime", "trigwidth", "corruption", "bxcounter",
	"bxcounter", "eventcounter", "orbitcounter" };

static std::vector<std::string> trig_mode_data_columns = {
	"event", "trigtime", "channelsumid", "rawsum", "decompresssum"
};

std::vector<std::string> filter_measurement_columns(bool event_mode, std::vector<std::string> columns) {
	std::vector<std::string> filtered_columns;
	std::vector<std::string> expected_columns;
	if ( event_mode ) {
		expected_columns = event_mode_data_columns;
	} else {
		expected_columns = summary_data_columns;
	}
	for (std::string &col: columns) {
		for (std::string &expected_col: expected_columns) {
			if (col == expected_col) {
				filtered_columns.push_back(col);
				break;
			}
		}
	}
	return filtered_columns;
}
