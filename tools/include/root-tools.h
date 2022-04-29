#ifndef _ROOT_TOOLS_H_
#define _ROOT_TOOLS_H_
#include <TFile.h>
#include <TTree.h>
#include <vector>
#include <iostream>
#include <string>
#include <string.h>
#include <hdf5.h>
template<typename T>
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
	void *get_pointer_to_entry(char *column_name) {
		if (strcmp(column_name, "event")) return (void *)&event;
		if (strcmp(column_name, "chip")) return (void *)&chip;
		if (strcmp(column_name, "half")) return (void *)&half;
		if (strcmp(column_name, "channel")) return (void *)&channel;
		if (strcmp(column_name, "adc")) return (void *)&adc;
		if (strcmp(column_name, "adcm")) return (void *)&adcm;
		if (strcmp(column_name, "toa")) return (void *)&toa;
		if (strcmp(column_name, "tot")) return (void *)&tot;
		if (strcmp(column_name, "totflag")) return (void *)&totflag;
		if (strcmp(column_name, "trigtime")) return (void *)&trigtime;
		if (strcmp(column_name, "trigwidth")) return (void *)&trigwidth;
		if (strcmp(column_name, "corruption")) return (void *)&corruption;
		if (strcmp(column_name, "bxcounter")) return (void *)&bxcounter;
		if (strcmp(column_name, "eventcounter")) return (void *)&eventcounter;
		if (strcmp(column_name, "orbitcounter")) return (void *)&orbitcounter;
		if (strcmp(column_name, "errorbit")) return (void *)&errorbit;
		if (strcmp(column_name, "channelsumid")) return (void *)&channelsumid;
		if (strcmp(column_name, "rawsum")) return (void *)&rawsum;
		if (strcmp(column_name, "decompresssum")) return (void *)&decompresssum;
		return NULL;
	};
	T get_value(char *column_name) {
		if (strcmp(column_name, "event")) return (T)event;
		if (strcmp(column_name, "chip")) return (T)chip;
		if (strcmp(column_name, "half")) return (T)half;
		if (strcmp(column_name, "channel")) return (T)channel;
		if (strcmp(column_name, "adc")) return (T)adc;
		if (strcmp(column_name, "adcm")) return (T)adcm;
		if (strcmp(column_name, "toa")) return (T)toa;
		if (strcmp(column_name, "tot")) return (T)tot;
		if (strcmp(column_name, "totflag")) return (T)totflag;
		if (strcmp(column_name, "trigtime")) return (T)trigtime;
		if (strcmp(column_name, "trigwidth")) return (T)trigwidth;
		if (strcmp(column_name, "corruption")) return (T)corruption;
		if (strcmp(column_name, "bxcounter")) return (T)bxcounter;
		if (strcmp(column_name, "eventcounter")) return (T)eventcounter;
		if (strcmp(column_name, "orbitcounter")) return (T)orbitcounter;
		if (strcmp(column_name, "errorbit")) return (T)errorbit;
		if (strcmp(column_name, "channelsumid")) return (T)channelsumid;
		if (strcmp(column_name, "rawsum")) return (T)rawsum;
		if (strcmp(column_name, "decompresssum")) return (T)decompresssum;
		return (T) 0;
	};
	hid_t get_hdf_type(char *column_name) {
		if (strcmp(column_name, "event")) return H5T_NATIVE_UINT;
		if (strcmp(column_name, "chip")) return H5T_NATIVE_UINT;
		if (strcmp(column_name, "half")) return H5T_NATIVE_UINT;
		if (strcmp(column_name, "channel")) return H5T_NATIVE_UINT;
		if (strcmp(column_name, "adc")) return H5T_NATIVE_UINT;
		if (strcmp(column_name, "adcm")) return H5T_NATIVE_UINT;
		if (strcmp(column_name, "toa")) return H5T_NATIVE_UINT;
		if (strcmp(column_name, "tot")) return H5T_NATIVE_UINT;
		if (strcmp(column_name, "totflag")) return H5T_NATIVE_UINT;
		if (strcmp(column_name, "trigtime")) return H5T_NATIVE_UINT;
		if (strcmp(column_name, "trigwidth")) return H5T_NATIVE_UINT;
		if (strcmp(column_name, "corruption")) return H5T_NATIVE_UINT;
		if (strcmp(column_name, "bxcounter")) return H5T_NATIVE_UINT;
		if (strcmp(column_name, "eventcounter")) return H5T_NATIVE_UINT;
		if (strcmp(column_name, "orbitcounter")) return H5T_NATIVE_UINT;
		if (strcmp(column_name, "errorbit")) return H5T_NATIVE_UINT;
		if (strcmp(column_name, "channelsumid")) return H5T_NATIVE_UINT;
		if (strcmp(column_name, "rawsum")) return H5T_NATIVE_UINT;
		if (strcmp(column_name, "decompresssum")) return H5T_NATIVE_FLOAT;
		return 0;
	}
};

template<typename T>
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
	void *get_pointer_to_entry(char *column_name) {
		if (strcmp(column_name, "chip")) return (void *)&chip;
		if (strcmp(column_name, "channel")) return (void *)&channel;
		if (strcmp(column_name, "channeltype")) return (void *)&channeltype;
		if (strcmp(column_name, "adc_median")) return (void *)&adc_median;
		if (strcmp(column_name, "adc_iqr")) return (void *)&adc_irq;
		if (strcmp(column_name, "tot_median")) return (void *)&tot_median;
		if (strcmp(column_name, "tot_iqr")) return (void *)&tot_irq;
		if (strcmp(column_name, "toa_median")) return (void *)&toa_median;
		if (strcmp(column_name, "toa_iqr")) return (void *)&toa_irq;
		if (strcmp(column_name, "toa_mean")) return (void *)&toa_mean;
		if (strcmp(column_name, "tot_mean")) return (void *)&tot_mean;
		if (strcmp(column_name, "adc_mean")) return (void *)&adc_mean;
		if (strcmp(column_name, "adc_stdd")) return (void *)&adc_stdd;
		if (strcmp(column_name, "toa_stdd")) return (void *)&toa_stdd;
		if (strcmp(column_name, "tot_stdd")) return (void *)&tot_stdd;
		if (strcmp(column_name, "tot_efficiency")) return (void *)&tot_efficiency;
		if (strcmp(column_name, "tot_efficiency_error")) return (void *)&tot_efficiency_error;
		if (strcmp(column_name, "toa_efficiency")) return (void *)&toa_efficiency;
		if (strcmp(column_name, "toa_efficiency_error")) return (void *)&toa_efficiency_error;
		return NULL;
	};
	T get_value(char *column_name){
		if (strcmp(column_name, "chip")) return (T) chip;
		if (strcmp(column_name, "channel")) return (T) channel;
		if (strcmp(column_name, "channeltype")) return (T) channeltype;
		if (strcmp(column_name, "adc_median")) return (T) adc_median;
		if (strcmp(column_name, "adc_iqr")) return (T) adc_irq;
		if (strcmp(column_name, "tot_median")) return (T) tot_median;
		if (strcmp(column_name, "tot_iqr")) return (T) tot_irq;
		if (strcmp(column_name, "toa_median")) return (T) toa_median;
		if (strcmp(column_name, "toa_iqr")) return (T) toa_irq;
		if (strcmp(column_name, "toa_mean")) return (T) toa_mean;
		if (strcmp(column_name, "tot_mean")) return (T) tot_mean;
		if (strcmp(column_name, "adc_mean")) return (T) adc_mean;
		if (strcmp(column_name, "adc_stdd")) return (T) adc_stdd;
		if (strcmp(column_name, "toa_stdd")) return (T) toa_stdd;
		if (strcmp(column_name, "tot_stdd")) return (T) tot_stdd;
		if (strcmp(column_name, "tot_efficiency")) return (T) tot_efficiency;
		if (strcmp(column_name, "tot_efficiency_error")) return (T) tot_efficiency_error;
		if (strcmp(column_name, "toa_efficiency")) return (T) toa_efficiency;
		if (strcmp(column_name, "toa_efficiency_error")) return (T) toa_efficiency_error;
		return (T) 0;
	};
	hid_t get_hdf_type(char *column_name){
		if (strcmp(column_name, "chip")) return H5T_NATIVE_INT;
		if (strcmp(column_name, "channel")) return H5T_NATIVE_SHORT; 
		if (strcmp(column_name, "channeltype")) return H5T_NATIVE_SHORT;
		if (strcmp(column_name, "adc_median")) return H5T_NATIVE_SHORT;
		if (strcmp(column_name, "adc_iqr")) return H5T_NATIVE_SHORT;
		if (strcmp(column_name, "tot_median")) return H5T_NATIVE_SHORT;
		if (strcmp(column_name, "tot_iqr")) return H5T_NATIVE_SHORT;
		if (strcmp(column_name, "toa_median")) return H5T_NATIVE_SHORT;
		if (strcmp(column_name, "toa_iqr")) return H5T_NATIVE_FLOAT;
		if (strcmp(column_name, "toa_mean")) return H5T_NATIVE_FLOAT;
		if (strcmp(column_name, "tot_mean")) return H5T_NATIVE_FLOAT;
		if (strcmp(column_name, "adc_mean")) return H5T_NATIVE_FLOAT;
		if (strcmp(column_name, "adc_stdd")) return H5T_NATIVE_FLOAT;
		if (strcmp(column_name, "toa_stdd")) return H5T_NATIVE_FLOAT;
		if (strcmp(column_name, "tot_stdd")) return H5T_NATIVE_FLOAT;
		if (strcmp(column_name, "tot_efficiency")) return H5T_NATIVE_FLOAT;
		if (strcmp(column_name, "tot_efficiency_error")) return H5T_NATIVE_FLOAT;
		if (strcmp(column_name, "toa_efficiency")) return H5T_NATIVE_FLOAT;
		if (strcmp(column_name, "toa_efficiency_error")) return H5T_NATIVE_FLOAT;
		return 0;
	};
};
std::vector<std::string> filter_measurement_columns(bool event_mode, std::vector<std::string> columns);
TTree *openRootTree(TFile *Measurements, std::string root_file_path, bool* event_mode);
#endif
