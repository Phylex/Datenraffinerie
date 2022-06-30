#ifndef _ROOT_TOOLS_H_
#define _ROOT_TOOLS_H_
#include <TFile.h>
#include <TTree.h>
#include <vector>
#include <iostream>
#include <string>
#include <string.h>
#include <hdf5.h>
struct hgcroc_data {
	int event;
	int chip;
	int half;
	int channel;
	int adc;
	int adcm;
	int tot;
	int toa;
	int totflag;
	int trigtime;
	int trigwidth;
	int corruption;
	int bxcounter;
	int eventcounter;
	int orbitcounter;
	int errorbit;
	int channelsumid;
	int rawsum;
	float decompresssum;
	char sizes[19] = {sizeof(event), sizeof(chip), sizeof(half), sizeof(channel), sizeof(adc), sizeof(adcm), sizeof(tot),
									sizeof(toa), sizeof(totflag), sizeof(trigtime), sizeof(trigwidth), sizeof(corruption), sizeof(bxcounter),
	                sizeof(eventcounter), sizeof(orbitcounter), sizeof(errorbit), sizeof(channelsumid), sizeof(rawsum), sizeof(decompresssum)};


	int get_index(const char *column_name) {
		if (!strcmp(column_name, "event")) return 0;
		if (!strcmp(column_name, "chip")) return 1;
		if (!strcmp(column_name, "half")) return 2;
		if (!strcmp(column_name, "channel")) return 3;
		if (!strcmp(column_name, "adc")) return 4;
		if (!strcmp(column_name, "adcm")) return 5;
		if (!strcmp(column_name, "toa")) return 6;
		if (!strcmp(column_name, "tot")) return 7;
		if (!strcmp(column_name, "totflag")) return 8;
		if (!strcmp(column_name, "trigtime")) return 9;
		if (!strcmp(column_name, "trigwidth")) return 10;
		if (!strcmp(column_name, "corruption")) return 11;
		if (!strcmp(column_name, "bxcounter")) return 12;
		if (!strcmp(column_name, "eventcounter")) return 13;
		if (!strcmp(column_name, "orbitcounter")) return 14;
		if (!strcmp(column_name, "errorbit")) return 15;
		if (!strcmp(column_name, "channelsumid")) return 16;
		if (!strcmp(column_name, "rawsum")) return 17;
		if (!strcmp(column_name, "decompresssum")) return 18;
		return -1;
	}

	void *get_pointer_to_entry(const char *column_name) {
		if (!strcmp(column_name, "event")) return (void *)&(this->event);
		if (!strcmp(column_name, "chip")) return (void *)&(this->chip);
		if (!strcmp(column_name, "half")) return (void *)&(this->half);
		if (!strcmp(column_name, "channel")) return (void *)&(this->channel);
		if (!strcmp(column_name, "adc")) return (void *)&(this->adc);
		if (!strcmp(column_name, "adcm")) return (void *)&(this->adcm);
		if (!strcmp(column_name, "toa")) return (void *)&(this->toa);
		if (!strcmp(column_name, "tot")) return (void *)&(this->tot);
		if (!strcmp(column_name, "totflag")) return (void *)&(this->totflag);
		if (!strcmp(column_name, "trigtime")) return (void *)&(this->trigtime);
		if (!strcmp(column_name, "trigwidth")) return (void *)&(this->trigwidth);
		if (!strcmp(column_name, "corruption")) return (void *)&(this->corruption);
		if (!strcmp(column_name, "bxcounter")) return (void *)&(this->bxcounter);
		if (!strcmp(column_name, "eventcounter")) return (void *)&(this->eventcounter);
		if (!strcmp(column_name, "orbitcounter")) return (void *)&(this->orbitcounter);
		if (!strcmp(column_name, "errorbit")) return (void *)&(this->errorbit);
		if (!strcmp(column_name, "channelsumid")) return (void *)&(this->channelsumid);
		if (!strcmp(column_name, "rawsum")) return (void *)&(this->rawsum);
		if (!strcmp(column_name, "decompresssum")) return (void *)&(this->decompresssum);
		return NULL;
	};
	size_t get_size(const char *column_name) {
		if (!strcmp(column_name, "event")) return sizeof(event);
		if (!strcmp(column_name, "chip")) return sizeof(chip);
		if (!strcmp(column_name, "half")) return sizeof(half);
		if (!strcmp(column_name, "channel")) return sizeof(channel);
		if (!strcmp(column_name, "adc")) return sizeof(adc);
		if (!strcmp(column_name, "adcm")) return sizeof(adcm);
		if (!strcmp(column_name, "toa")) return sizeof(toa);
		if (!strcmp(column_name, "tot")) return sizeof(tot);
		if (!strcmp(column_name, "totflag")) return sizeof(totflag);
		if (!strcmp(column_name, "trigtime")) return sizeof(trigtime);
		if (!strcmp(column_name, "trigwidth")) return sizeof(trigwidth);
		if (!strcmp(column_name, "corruption")) return sizeof(corruption);
		if (!strcmp(column_name, "bxcounter")) return sizeof(bxcounter);
		if (!strcmp(column_name, "eventcounter")) return sizeof(eventcounter);
		if (!strcmp(column_name, "orbitcounter")) return sizeof(orbitcounter);
		if (!strcmp(column_name, "errorbit")) return sizeof(errorbit);
		if (!strcmp(column_name, "channelsumid")) return sizeof(channelsumid);
		if (!strcmp(column_name, "rawsum")) return sizeof(rawsum);
		if (!strcmp(column_name, "decompresssum")) return sizeof(decompresssum);
		return 0;
	};
	hid_t get_hdf_type(const char *column_name) {
		if (!strcmp(column_name, "event")) return H5T_NATIVE_UINT;
		if (!strcmp(column_name, "chip")) return H5T_NATIVE_UINT;
		if (!strcmp(column_name, "half")) return H5T_NATIVE_UINT;
		if (!strcmp(column_name, "channel")) return H5T_NATIVE_UINT;
		if (!strcmp(column_name, "adc")) return H5T_NATIVE_UINT;
		if (!strcmp(column_name, "adcm")) return H5T_NATIVE_UINT;
		if (!strcmp(column_name, "toa")) return H5T_NATIVE_UINT;
		if (!strcmp(column_name, "tot")) return H5T_NATIVE_UINT;
		if (!strcmp(column_name, "totflag")) return H5T_NATIVE_UINT;
		if (!strcmp(column_name, "trigtime")) return H5T_NATIVE_UINT;
		if (!strcmp(column_name, "trigwidth")) return H5T_NATIVE_UINT;
		if (!strcmp(column_name, "corruption")) return H5T_NATIVE_UINT;
		if (!strcmp(column_name, "bxcounter")) return H5T_NATIVE_UINT;
		if (!strcmp(column_name, "eventcounter")) return H5T_NATIVE_UINT;
		if (!strcmp(column_name, "orbitcounter")) return H5T_NATIVE_UINT;
		if (!strcmp(column_name, "errorbit")) return H5T_NATIVE_UINT;
		if (!strcmp(column_name, "channelsumid")) return H5T_NATIVE_UINT;
		if (!strcmp(column_name, "rawsum")) return H5T_NATIVE_UINT;
		if (!strcmp(column_name, "decompresssum")) return H5T_NATIVE_FLOAT;
		return 0;
	}
};

struct hgcroc_summary_data {
	int chip;
	short channel;
	short channeltype;
	short adc_median;
	short adc_irq;
	short tot_median;
	short tot_irq;
	short toa_median;
	short toa_irq;
	float adc_mean;
	float adc_stdd;
	float tot_mean;
	float tot_stdd;
	float tot_efficiency;
	float tot_efficiency_error;
	float toa_mean;
	float toa_stdd;
	float toa_efficiency;
	float toa_efficiency_error;
	void *get_pointer_to_entry(const char *column_name) {
		if (!strcmp(column_name, "chip")) return (void *)&(this->chip);
		if (!strcmp(column_name, "channel")) return (void *)&(this->channel);
		if (!strcmp(column_name, "channeltype")) return (void *)&(this->channeltype);
		if (!strcmp(column_name, "adc_median")) return (void *)&(this->adc_median);
		if (!strcmp(column_name, "adc_iqr")) return (void *)&(this->adc_irq);
		if (!strcmp(column_name, "tot_median")) return (void *)&(this->tot_median);
		if (!strcmp(column_name, "tot_iqr")) return (void *)&(this->tot_irq);
		if (!strcmp(column_name, "toa_median")) return (void *)&(this->toa_median);
		if (!strcmp(column_name, "toa_iqr")) return (void *)&(this->toa_irq);
		if (!strcmp(column_name, "toa_mean")) return (void *)&(this->toa_mean);
		if (!strcmp(column_name, "tot_mean")) return (void *)&(this->tot_mean);
		if (!strcmp(column_name, "adc_mean")) return (void *)&(this->adc_mean);
		if (!strcmp(column_name, "adc_stdd")) return (void *)&(this->adc_stdd);
		if (!strcmp(column_name, "toa_stdd")) return (void *)&(this->toa_stdd);
		if (!strcmp(column_name, "tot_stdd")) return (void *)&(this->tot_stdd);
		if (!strcmp(column_name, "tot_efficiency")) return (void *)&(this->tot_efficiency);
		if (!strcmp(column_name, "tot_efficiency_error")) return (void *)&(this->tot_efficiency_error);
		if (!strcmp(column_name, "toa_efficiency")) return (void *)&(this->toa_efficiency);
		if (!strcmp(column_name, "toa_efficiency_error")) return (void *)&(this->toa_efficiency_error);
		return NULL;
	};
	size_t get_size(const char *column_name){
		if (!strcmp(column_name, "chip")) return sizeof(chip);
		if (!strcmp(column_name, "channel")) return sizeof(channel);
		if (!strcmp(column_name, "channeltype")) return sizeof(channeltype);
		if (!strcmp(column_name, "adc_median")) return sizeof(adc_median);
		if (!strcmp(column_name, "adc_iqr")) return sizeof(adc_irq);
		if (!strcmp(column_name, "tot_median")) return sizeof(tot_median);
		if (!strcmp(column_name, "tot_iqr")) return sizeof(tot_irq);
		if (!strcmp(column_name, "toa_median")) return sizeof(toa_median);
		if (!strcmp(column_name, "toa_iqr")) return sizeof(toa_irq);
		if (!strcmp(column_name, "toa_mean")) return sizeof(toa_mean);
		if (!strcmp(column_name, "tot_mean")) return sizeof(tot_mean);
		if (!strcmp(column_name, "adc_mean")) return sizeof(adc_mean);
		if (!strcmp(column_name, "adc_stdd")) return sizeof(adc_stdd);
		if (!strcmp(column_name, "toa_stdd")) return sizeof(toa_stdd);
		if (!strcmp(column_name, "tot_stdd")) return sizeof(tot_stdd);
		if (!strcmp(column_name, "tot_efficiency")) return sizeof(tot_efficiency);
		if (!strcmp(column_name, "tot_efficiency_error")) return sizeof(tot_efficiency_error);
		if (!strcmp(column_name, "toa_efficiency")) return sizeof(toa_efficiency);
		if (!strcmp(column_name, "toa_efficiency_error")) return sizeof(toa_efficiency_error);
		return 0;
	};
	hid_t get_hdf_type(const char *column_name){
		if (!strcmp(column_name, "chip")) return H5T_NATIVE_INT;
		if (!strcmp(column_name, "channel")) return H5T_NATIVE_SHORT; 
		if (!strcmp(column_name, "channeltype")) return H5T_NATIVE_SHORT;
		if (!strcmp(column_name, "adc_median")) return H5T_NATIVE_SHORT;
		if (!strcmp(column_name, "adc_iqr")) return H5T_NATIVE_SHORT;
		if (!strcmp(column_name, "tot_median")) return H5T_NATIVE_SHORT;
		if (!strcmp(column_name, "tot_iqr")) return H5T_NATIVE_SHORT;
		if (!strcmp(column_name, "toa_median")) return H5T_NATIVE_SHORT;
		if (!strcmp(column_name, "toa_iqr")) return H5T_NATIVE_FLOAT;
		if (!strcmp(column_name, "toa_mean")) return H5T_NATIVE_FLOAT;
		if (!strcmp(column_name, "tot_mean")) return H5T_NATIVE_FLOAT;
		if (!strcmp(column_name, "adc_mean")) return H5T_NATIVE_FLOAT;
		if (!strcmp(column_name, "adc_stdd")) return H5T_NATIVE_FLOAT;
		if (!strcmp(column_name, "toa_stdd")) return H5T_NATIVE_FLOAT;
		if (!strcmp(column_name, "tot_stdd")) return H5T_NATIVE_FLOAT;
		if (!strcmp(column_name, "tot_efficiency")) return H5T_NATIVE_FLOAT;
		if (!strcmp(column_name, "tot_efficiency_error")) return H5T_NATIVE_FLOAT;
		if (!strcmp(column_name, "toa_efficiency")) return H5T_NATIVE_FLOAT;
		if (!strcmp(column_name, "toa_efficiency_error")) return H5T_NATIVE_FLOAT;
		return 0;
	};
};
std::vector<std::string> filter_measurement_columns(bool event_mode, std::vector<std::string> columns);
TTree *openRootTree(TFile *Measurements, std::string root_file_path, bool* event_mode);
#endif
