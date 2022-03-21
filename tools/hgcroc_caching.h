#ifndef _HGCROC_CACHING_H_
#define _HGCROC_CACHING_H_
#include <yaml-cpp/yaml.h>
#include <map>
#include <tuple>
#include <vector>
#include <array>

#define ROC_CHAN_COUNT 72
#define ROC_CHAN_TYPE 0
#define ROC_CALIB_CHAN_COUNT 4
#define ROC_CALIB_CHAN_TYPE 1
#define ROC_CM_CHAN_COUNT 2
#define ROC_CM_CHAN_TYPE 100

static const std::array<unsigned int, 3> channel_types = {
	ROC_CHAN_TYPE,
	ROC_CALIB_CHAN_TYPE,
	ROC_CM_CHAN_TYPE
};

static std::map<unsigned int, std::string> channel_type_map = {
	{ROC_CHAN_TYPE, "ch"},
	{ROC_CALIB_CHAN_TYPE, "calib"},
	{ROC_CM_CHAN_TYPE, "cm"}
};

static std::map<unsigned int, int> channel_type_to_channel_cout = {
	{ROC_CHAN_TYPE, ROC_CHAN_COUNT},
	{ROC_CM_CHAN_TYPE, ROC_CM_CHAN_COUNT},
	{ROC_CALIB_CHAN_TYPE, ROC_CALIB_CHAN_COUNT}
};

static std::map<unsigned int, std::string> chip_num_to_name = {
	{0, "roc_s0"},
	{1, "roc_s1"},
	{2, "roc_s2"},
	{3, "roc_s3"},
	{4, "roc_s4"},
	{5, "roc_s5"}
};

static const std::array<std::pair<std::string, std::string>, 159> roc_half_config = {
	{"ReferenceVoltage", "Calib"},
	{"ReferenceVoltage", "ExtCtest"},
	{"ReferenceVoltage", "IntCtest"},
	{"ReferenceVoltage", "Inv_vref"},
	{"ReferenceVoltage", "Noinv_vref"},
	{"ReferenceVoltage", "ON_dac"},
	{"ReferenceVoltage", "Refi"},
	{"ReferenceVoltage", "Toa_vref"},
	{"ReferenceVoltage", "Tot_vref"},
	{"ReferenceVoltage", "Vbg_1v"},
	{"ReferenceVoltage", "probe_dc"},
	{"ReferenceVoltage", "probe_dc1"},
	{"ReferenceVoltage", "probe_dc2"},
	{"MasterTdc", "BIAS_CAL_DAC_CTDC_P_D"},
	{"MasterTdc", "BIAS_CAL_DAC_CTDC_P_EN"},
	{"MasterTdc", "BIAS_FOLLOWER_CAL_P_CTDC_EN"},
	{"MasterTdc", "BIAS_FOLLOWER_CAL_P_D"},
	{"MasterTdc", "BIAS_FOLLOWER_CAL_P_FTDC_D"},
	{"MasterTdc", "BIAS_FOLLOWER_CAL_P_FTDC_EN"},
	{"MasterTdc", "BIAS_I_CTDC_D"},
	{"MasterTdc", "BIAS_I_FTDC_D"},
	{"MasterTdc", "CALIB_CHANNEL_DLL"},
	{"MasterTdc", "CTDC_CALIB_FREQUENCY"},
	{"MasterTdc", "CTRL_IN_REF_CTDC_P_D"},
	{"MasterTdc", "CTRL_IN_REF_CTDC_P_EN"},
	{"MasterTdc", "CTRL_IN_REF_FTDC_P_D"},
	{"MasterTdc", "CTRL_IN_REF_FTDC_P_EN"},
	{"MasterTdc", "CTRL_IN_SIG_CTDC_P_D"},
	{"MasterTdc", "CTRL_IN_SIG_CTDC_P_EN"},
	{"MasterTdc", "CTRL_IN_SIG_FTDC_P_D"},
	{"MasterTdc", "CTRL_IN_SIG_FTDC_P_EN"},
	{"MasterTdc", "EN_MASTER_CTDC_DLL"},
	{"MasterTdc", "EN_MASTER_CTDC_VOUT_INIT"},
	{"MasterTdc", "EN_MASTER_FTDC_DLL"},
	{"MasterTdc", "EN_MASTER_FTDC_VOUT_INIT"},
	{"MasterTdc", "EN_REF_BG"},
	{"MasterTdc", "FOLLOWER_CTDC_EN"},
	{"MasterTdc", "FOLLOWER_FTDC_EN"},
	{"MasterTdc", "FTDC_CALIB_FREQUENCY"},
	{"MasterTdc", "GLOBAL_DISABLE_TOT_LIMIT"},
	{"MasterTdc", "GLOBAL_EN_BUFFER_CTDC"},
	{"MasterTdc", "GLOBAL_EN_BUFFER_FTDC"},
	{"MasterTdc", "GLOBAL_EN_TOT_PRIORITY"},
	{"MasterTdc", "GLOBAL_EN_TUNE_GAIN_DAC"},
	{"MasterTdc", "GLOBAL_FORCE_EN_CLK"},
	{"MasterTdc", "GLOBAL_FORCE_EN_OUTPUT_DATA"},
	{"MasterTdc", "GLOBAL_FORCE_EN_TOT"},
	{"MasterTdc", "GLOBAL_INIT_DAC_B_CTDC"},
	{"MasterTdc", "GLOBAL_LATENCY_TIME"},
	{"MasterTdc", "GLOBAL_MODE_FTDC_TOA"},
	{"MasterTdc", "GLOBAL_MODE_NO_TOT_SUB"},
	{"MasterTdc", "GLOBAL_MODE_TOA_DIRECT_OUTPUT"},
	{"MasterTdc", "GLOBAL_SEU_TIME_OUT"},
	{"MasterTdc", "GLOBAL_TA_SELECT_GAIN_TOA"},
	{"MasterTdc", "GLOBAL_TA_SELECT_GAIN_TOT"},
	{"MasterTdc", "INV_FRONT_40MHZ"},
	{"MasterTdc", "START_COUNTER"},
	{"MasterTdc", "VD_CTDC_N_D"},
	{"MasterTdc", "VD_CTDC_N_DAC_EN"},
	{"MasterTdc", "VD_CTDC_N_FORCE_MAX"},
	{"MasterTdc", "VD_CTDC_P_D"},
	{"MasterTdc", "VD_CTDC_P_DAC_EN"},
	{"MasterTdc", "VD_FTDC_N_D"},
	{"MasterTdc", "VD_FTDC_N_DAC_EN"},
	{"MasterTdc", "VD_FTDC_N_FORCE_MAX"},
	{"MasterTdc", "VD_FTDC_P_D"},
	{"MasterTdc", "VD_FTDC_P_DAC_EN"},
	{"MasterTdc", "sel_clk_rcg"},
	{"HalfWise", "Adc_pedestal"},
	{"HalfWise", "Channel_off"},
	{"HalfWise", "DAC_CAL_CTDC_TOA"},
	{"HalfWise", "DAC_CAL_CTDC_TOT"},
	{"HalfWise", "DAC_CAL_FTDC_TOA"},
	{"HalfWise", "DAC_CAL_FTDC_TOT"},
	{"HalfWise", "DIS_TDC"},
	{"HalfWise", "ExtData"},
	{"HalfWise", "HZ_inv"},
	{"HalfWise", "HZ_noinv"},
	{"HalfWise", "HighRange"},
	{"HalfWise", "IN_FTDC_ENCODER_TOA"},
	{"HalfWise", "IN_FTDC_ENCODER_TOT"},
	{"HalfWise", "Inputdac"},
	{"HalfWise", "LowRange"},
	{"HalfWise", "mask_AlignBuffer"},
	{"HalfWise", "mask_adc"},
	{"HalfWise", "mask_toa"},
	{"HalfWise", "mask_tot"},
	{"HalfWise", "probe_inv"},
	{"HalfWise", "probe_noinv"},
	{"HalfWise", "probe_pa"},
	{"HalfWise", "probe_toa"},
	{"HalfWise", "probe_tot"},
	{"HalfWise", "sel_trig_toa"},
	{"HalfWise", "sel_trig_tot"},
	{"HalfWise", "trim_inv"},
	{"HalfWise", "trim_toa"},
	{"HalfWise", "trim_tot"},
	{"GlobalAnalog", "Cf"},
	{"GlobalAnalog", "Cf_comp"},
	{"GlobalAnalog", "Clr_ADC"},
	{"GlobalAnalog", "Clr_ShaperTail"},
	{"GlobalAnalog", "Delay40"},
	{"GlobalAnalog", "Delay65"},
	{"GlobalAnalog", "Delay87"},
	{"GlobalAnalog", "Delay9"},
	{"GlobalAnalog", "En_hyst_tot"},
	{"GlobalAnalog", "Ibi_inv"},
	{"GlobalAnalog", "Ibi_inv_buf"},
	{"GlobalAnalog", "Ibi_noinv"},
	{"GlobalAnalog", "Ibi_noinv_buf"},
	{"GlobalAnalog", "Ibi_sk"},
	{"GlobalAnalog", "Ibo_inv"},
	{"GlobalAnalog", "Ibo_inv_buf"},
	{"GlobalAnalog", "Ibo_noinv"},
	{"GlobalAnalog", "Ibo_noinv_buf"},
	{"GlobalAnalog", "Ibo_sk"},
	{"GlobalAnalog", "ON_pa"},
	{"GlobalAnalog", "ON_ref_adc"},
	{"GlobalAnalog", "ON_rtr"},
	{"GlobalAnalog", "ON_toa"},
	{"GlobalAnalog", "ON_tot"},
	{"GlobalAnalog", "Rc"},
	{"GlobalAnalog", "Rf"},
	{"GlobalAnalog", "S_inv"},
	{"GlobalAnalog", "S_inv_buf"},
	{"GlobalAnalog", "S_noinv"},
	{"GlobalAnalog", "S_noinv_buf"},
	{"GlobalAnalog", "S_sk"},
	{"GlobalAnalog", "SelExtADC"},
	{"GlobalAnalog", "SelRisingEdge"},
	{"GlobalAnalog", "dac_pol"},
	{"GlobalAnalog", "gain_tot"},
	{"GlobalAnalog", "neg"},
	{"GlobalAnalog", "pol_trig_toa"},
	{"GlobalAnalog", "range_indac"},
	{"GlobalAnalog", "range_inv"},
	{"GlobalAnalog", "range_tot"},
	{"GlobalAnalog", "ref_adc"},
	{"GlobalAnalog", "trim_vbi_pa"},
	{"GlobalAnalog", "trim_vbo_pa"},
	{"DigitalHalf", "Adc_TH"},
	{"DigitalHalf", "Bx_offset"},
	{"DigitalHalf", "Bx_trigger"},
	{"DigitalHalf", "CalibrationSC"},
	{"DigitalHalf", "ClrAdcTot_trig"},
	{"DigitalHalf", "IdleFrame"},
	{"DigitalHalf", "L1Offset"},
	{"DigitalHalf", "MultFactor"},
	{"DigitalHalf", "SC_testRAM"},
	{"DigitalHalf", "SelTC4"},
	{"DigitalHalf", "Tot_P0"},
	{"DigitalHalf", "Tot_P1"},
	{"DigitalHalf", "Tot_P2"},
	{"DigitalHalf", "Tot_P3"},
	{"DigitalHalf", "Tot_P_Add"},
	{"DigitalHalf", "Tot_TH0"},
	{"DigitalHalf", "Tot_TH1"},
	{"DigitalHalf", "Tot_TH2"},
	{"DigitalHalf", "Tot_TH3"},
	{"DigitalHalf", "sc_testRAM"},
};

static std::array<std::tuple<std::string, std::string>, 42> roc_global_config = {
	{"Top", "BIAS_I_PLL_D"},
	{"Top", "DIV_PLL"},
	{"Top", "EN"},
	{"Top", "EN_HIGH_CAPA"},
	{"Top", "EN_LOCK_CONTROL"},
	{"Top", "EN_PLL"},
	{"Top", "EN_PhaseShift"},
	{"Top", "EN_RCG"},
	{"Top", "EN_REF_BG"},
	{"Top", "EN_probe_pll"},
	{"Top", "ENpE"},
	{"Top", "ERROR_LIMIT_SC"},
	{"Top", "EdgeSel_T1"},
	{"Top", "FOLLOWER_PLL_EN"},
	{"Top", "INIT_D"},
	{"Top", "INIT_DAC_EN"},
	{"Top", "Pll_Locked_sc"},
	{"Top", "PreL1AOffset"},
	{"Top", "RunL"},
	{"Top", "RunR"},
	{"Top", "S"},
	{"Top", "TestMode"},
	{"Top", "VOUT_INIT_EN"},
	{"Top", "VOUT_INIT_EXT_D"},
	{"Top", "VOUT_INIT_EXT_EN"},
	{"Top", "b_in"},
	{"Top", "b_out"},
	{"Top", "err_countR"},
	{"Top", "fc_error_count"},
	{"Top", "in_inv_cmd_rx"},
	{"Top", "lock_count"},
	{"Top", "n_counter_rst"},
	{"Top", "phase_ck"},
	{"Top", "phase_strobe"},
	{"Top", "rcg_gain"},
	{"Top", "sel_40M_ext"},
	{"Top", "sel_error"},
	{"Top", "sel_lock"},
	{"Top", "sel_strobe_ext"},
	{"Top", "srout"},
	{"Top", "statusL"},
	{"Top", "statusR"}
};

static std::array<std::string, 29> chan_config_params = {
      "Adc_pedestal",
      "Channel_off",
      "DAC_CAL_CTDC_TOA",
      "DAC_CAL_CTDC_TOT",
      "DAC_CAL_FTDC_TOA",
      "DAC_CAL_FTDC_TOT",
      "DIS_TDC",
      "ExtData",
      "HZ_inv",
      "HZ_noinv",
      "HighRange",
      "IN_FTDC_ENCODER_TOA",
      "IN_FTDC_ENCODER_TOT",
      "Inputdac",
      "LowRange",
      "mask_AlignBuffer",
      "mask_adc",
      "mask_toa",
      "mask_tot",
      "probe_inv",
      "probe_noinv",
      "probe_pa",
      "probe_toa",
      "probe_tot",
      "sel_trig_toa",
      "sel_trig_tot",
      "trim_inv",
      "trim_toa",
      "trim_tot",
};

using CacheKey = std::tuple<unsigned int, unsigned int, unsigned int>;
using GlobalCacheKey = unsigned int;
using HalfWiseCacheKey = std::tuple<unsigned int, unsigned int>;

template<typename T>
std::map<CacheKey, std::vector<T>> generate_hgcroc_chan_config_cache(YAML::Node config, std::vector<std::string> channel_columns){
	// allocate the result
	std::map<CacheKey, std::vector<T>> channel_map;
	std::vector<std::string> roc_names;
	
	// generate the roc keys for generating the config
	if (config.size() >= 3) {
		roc_names.push_back("roc_s0");
		roc_names.push_back("roc_s1");
		roc_names.push_back("roc_s2");
	} if (config.size() == 6) {
		roc_names.push_back("roc_s3");
		roc_names.push_back("roc_s4");
		roc_names.push_back("roc_s5");
	}
	
	// iterate over the rocs
	for (size_t roc=0; roc < roc_names.size(); roc++) {
		//iterate over the differernt types of channels
		for (auto chan_type: channel_types) {
			// iterate over each channel of the particular type
			for (size_t chan=0; chan < channel_type_to_channel_cout[chan_type]; chan++) {
				CacheKey key(roc, chan, chan_type);
				std::vector<T> channel_config_cache;
				channel_config_cache.reserve(channel_columns.size());
				
				// iterate over the selected parameters creating the entry
				for (auto column: channel_columns) {
					 channel_config_cache.push_back(config[roc_names[roc]][channel_type_map[chan_type]][chan][column].as<T>());
				}
				// add the cache to the cached config to the map
				channel_map[key] = channel_config_cache;
			}
		}
	}
	return channel_map;
};

template<typename T>
std::map<GlobalCacheKey, std::vector<T>> generate_hgcroc_global_config(YAML::Node config, std::vector<std::tuple<std::string, std::string>> global_columns) {
	std::map<GlobalCacheKey, std::vector<T>> global_config_cache;
	for (unsigned int i = 0; i < config.size(); i ++) {
		YAML::Node chip_config = config[chip_num_to_name[i]];
		// iterate over the global columns
		std::vector<T> global_cache_row;
		global_cache_row.reserve(global_columns.size());
		for (auto g_column: global_columns) {
			global_cache_row.push_back(chip_config[std::get<0>(g_column)][0][std::get<1>(g_column)]);
		}
		global_config_cache[i] = global_cache_row;
	}
	return global_config_cache;
};

template<typename T>
std::map<HalfWiseCacheKey, std::vector<T>> generate_hgcroc_halfwise_config(YAML::Node config, std::vector<std::tuple<std::string, std::string>> half_wise_columns) {
	std::map<HalfWiseCacheKey, std::vector<T>> half_wise_config_cache;
	for (unsigned int i = 0; i < config.size(); i ++) {
		YAML::Node chip_config = config[chip_num_to_name[i]];
		// iterate over the global columns
		std::vector<T> halfwise_cache_row;
		halfwise_cache_row.reserve(half_wise_columns.size());
		for (unsigned int j = 0; j < 2; j ++) {
			HalfWiseCacheKey key = {i, j};
			for (auto hw_column: half_wise_columns) {
				halfwise_cache_row.push_back(chip_config[std::get<0>(hw_column)][j][std::get<1>(hw_column)].as<T>());
			}
			half_wise_config_cache[key] = halfwise_cache_row;
		}
	}
	return half_wise_config_cache;
};
#endif
