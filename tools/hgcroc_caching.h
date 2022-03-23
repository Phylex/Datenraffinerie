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

static std::array<std::tuple<std::string, std::string>, 160> roc_half_config = {
	std::make_tuple("ReferenceVoltage", "Calib"),
	std::make_tuple("ReferenceVoltage", "ExtCtest"),
	std::make_tuple("ReferenceVoltage", "IntCtest"),
	std::make_tuple("ReferenceVoltage", "Inv_vref"),
	std::make_tuple("ReferenceVoltage", "Noinv_vref"),
	std::make_tuple("ReferenceVoltage", "ON_dac"),
	std::make_tuple("ReferenceVoltage", "Refi"),
	std::make_tuple("ReferenceVoltage", "Toa_vref"),
	std::make_tuple("ReferenceVoltage", "Tot_vref"),
	std::make_tuple("ReferenceVoltage", "Vbg_1v"),
	std::make_tuple("ReferenceVoltage", "probe_dc"),
	std::make_tuple("ReferenceVoltage", "probe_dc1"),
	std::make_tuple("ReferenceVoltage", "probe_dc2"),
	std::make_tuple("MasterTdc", "BIAS_CAL_DAC_CTDC_P_D"),
	std::make_tuple("MasterTdc", "BIAS_CAL_DAC_CTDC_P_EN"),
	std::make_tuple("MasterTdc", "BIAS_FOLLOWER_CAL_P_CTDC_EN"),
	std::make_tuple("MasterTdc", "BIAS_FOLLOWER_CAL_P_D"),
	std::make_tuple("MasterTdc", "BIAS_FOLLOWER_CAL_P_FTDC_D"),
	std::make_tuple("MasterTdc", "BIAS_FOLLOWER_CAL_P_FTDC_EN"),
	std::make_tuple("MasterTdc", "BIAS_I_CTDC_D"),
	std::make_tuple("MasterTdc", "BIAS_I_FTDC_D"),
	std::make_tuple("MasterTdc", "CALIB_CHANNEL_DLL"),
	std::make_tuple("MasterTdc", "CTDC_CALIB_FREQUENCY"),
	std::make_tuple("MasterTdc", "CTRL_IN_REF_CTDC_P_D"),
	std::make_tuple("MasterTdc", "CTRL_IN_REF_CTDC_P_EN"),
	std::make_tuple("MasterTdc", "CTRL_IN_REF_FTDC_P_D"),
	std::make_tuple("MasterTdc", "CTRL_IN_REF_FTDC_P_EN"),
	std::make_tuple("MasterTdc", "CTRL_IN_SIG_CTDC_P_D"),
	std::make_tuple("MasterTdc", "CTRL_IN_SIG_CTDC_P_EN"),
	std::make_tuple("MasterTdc", "CTRL_IN_SIG_FTDC_P_D"),
	std::make_tuple("MasterTdc", "CTRL_IN_SIG_FTDC_P_EN"),
	std::make_tuple("MasterTdc", "EN_MASTER_CTDC_DLL"),
	std::make_tuple("MasterTdc", "EN_MASTER_CTDC_VOUT_INIT"),
	std::make_tuple("MasterTdc", "EN_MASTER_FTDC_DLL"),
	std::make_tuple("MasterTdc", "EN_MASTER_FTDC_VOUT_INIT"),
	std::make_tuple("MasterTdc", "EN_REF_BG"),
	std::make_tuple("MasterTdc", "FOLLOWER_CTDC_EN"),
	std::make_tuple("MasterTdc", "FOLLOWER_FTDC_EN"),
	std::make_tuple("MasterTdc", "FTDC_CALIB_FREQUENCY"),
	std::make_tuple("MasterTdc", "GLOBAL_DISABLE_TOT_LIMIT"),
	std::make_tuple("MasterTdc", "GLOBAL_EN_BUFFER_CTDC"),
	std::make_tuple("MasterTdc", "GLOBAL_EN_BUFFER_FTDC"),
	std::make_tuple("MasterTdc", "GLOBAL_EN_TOT_PRIORITY"),
	std::make_tuple("MasterTdc", "GLOBAL_EN_TUNE_GAIN_DAC"),
	std::make_tuple("MasterTdc", "GLOBAL_FORCE_EN_CLK"),
	std::make_tuple("MasterTdc", "GLOBAL_FORCE_EN_OUTPUT_DATA"),
	std::make_tuple("MasterTdc", "GLOBAL_FORCE_EN_TOT"),
	std::make_tuple("MasterTdc", "GLOBAL_INIT_DAC_B_CTDC"),
	std::make_tuple("MasterTdc", "GLOBAL_LATENCY_TIME"),
	std::make_tuple("MasterTdc", "GLOBAL_MODE_FTDC_TOA"),
	std::make_tuple("MasterTdc", "GLOBAL_MODE_NO_TOT_SUB"),
	std::make_tuple("MasterTdc", "GLOBAL_MODE_TOA_DIRECT_OUTPUT"),
	std::make_tuple("MasterTdc", "GLOBAL_SEU_TIME_OUT"),
	std::make_tuple("MasterTdc", "GLOBAL_TA_SELECT_GAIN_TOA"),
	std::make_tuple("MasterTdc", "GLOBAL_TA_SELECT_GAIN_TOT"),
	std::make_tuple("MasterTdc", "INV_FRONT_40MHZ"),
	std::make_tuple("MasterTdc", "START_COUNTER"),
	std::make_tuple("MasterTdc", "VD_CTDC_N_D"),
	std::make_tuple("MasterTdc", "VD_CTDC_N_DAC_EN"),
	std::make_tuple("MasterTdc", "VD_CTDC_N_FORCE_MAX"),
	std::make_tuple("MasterTdc", "VD_CTDC_P_D"),
	std::make_tuple("MasterTdc", "VD_CTDC_P_DAC_EN"),
	std::make_tuple("MasterTdc", "VD_FTDC_N_D"),
	std::make_tuple("MasterTdc", "VD_FTDC_N_DAC_EN"),
	std::make_tuple("MasterTdc", "VD_FTDC_N_FORCE_MAX"),
	std::make_tuple("MasterTdc", "VD_FTDC_P_D"),
	std::make_tuple("MasterTdc", "VD_FTDC_P_DAC_EN"),
	std::make_tuple("MasterTdc", "sel_clk_rcg"),
	std::make_tuple("HalfWise", "Adc_pedestal"),
	std::make_tuple("HalfWise", "Channel_off"),
	std::make_tuple("HalfWise", "DAC_CAL_CTDC_TOA"),
	std::make_tuple("HalfWise", "DAC_CAL_CTDC_TOT"),
	std::make_tuple("HalfWise", "DAC_CAL_FTDC_TOA"),
	std::make_tuple("HalfWise", "DAC_CAL_FTDC_TOT"),
	std::make_tuple("HalfWise", "DIS_TDC"),
	std::make_tuple("HalfWise", "ExtData"),
	std::make_tuple("HalfWise", "HZ_inv"),
	std::make_tuple("HalfWise", "HZ_noinv"),
	std::make_tuple("HalfWise", "HighRange"),
	std::make_tuple("HalfWise", "IN_FTDC_ENCODER_TOA"),
	std::make_tuple("HalfWise", "IN_FTDC_ENCODER_TOT"),
	std::make_tuple("HalfWise", "Inputdac"),
	std::make_tuple("HalfWise", "LowRange"),
	std::make_tuple("HalfWise", "mask_AlignBuffer"),
	std::make_tuple("HalfWise", "mask_adc"),
	std::make_tuple("HalfWise", "mask_toa"),
	std::make_tuple("HalfWise", "mask_tot"),
	std::make_tuple("HalfWise", "probe_inv"),
	std::make_tuple("HalfWise", "probe_noinv"),
	std::make_tuple("HalfWise", "probe_pa"),
	std::make_tuple("HalfWise", "probe_toa"),
	std::make_tuple("HalfWise", "probe_tot"),
	std::make_tuple("HalfWise", "sel_trig_toa"),
	std::make_tuple("HalfWise", "sel_trig_tot"),
	std::make_tuple("HalfWise", "trim_inv"),
	std::make_tuple("HalfWise", "trim_toa"),
	std::make_tuple("HalfWise", "trim_tot"),
	std::make_tuple("GlobalAnalog", "Cf"),
	std::make_tuple("GlobalAnalog", "Cf_comp"),
	std::make_tuple("GlobalAnalog", "Clr_ADC"),
	std::make_tuple("GlobalAnalog", "Clr_ShaperTail"),
	std::make_tuple("GlobalAnalog", "Delay40"),
	std::make_tuple("GlobalAnalog", "Delay65"),
	std::make_tuple("GlobalAnalog", "Delay87"),
	std::make_tuple("GlobalAnalog", "Delay9"),
	std::make_tuple("GlobalAnalog", "En_hyst_tot"),
	std::make_tuple("GlobalAnalog", "Ibi_inv"),
	std::make_tuple("GlobalAnalog", "Ibi_inv_buf"),
	std::make_tuple("GlobalAnalog", "Ibi_noinv"),
	std::make_tuple("GlobalAnalog", "Ibi_noinv_buf"),
	std::make_tuple("GlobalAnalog", "Ibi_sk"),
	std::make_tuple("GlobalAnalog", "Ibo_inv"),
	std::make_tuple("GlobalAnalog", "Ibo_inv_buf"),
	std::make_tuple("GlobalAnalog", "Ibo_noinv"),
	std::make_tuple("GlobalAnalog", "Ibo_noinv_buf"),
	std::make_tuple("GlobalAnalog", "Ibo_sk"),
	std::make_tuple("GlobalAnalog", "ON_pa"),
	std::make_tuple("GlobalAnalog", "ON_ref_adc"),
	std::make_tuple("GlobalAnalog", "ON_rtr"),
	std::make_tuple("GlobalAnalog", "ON_toa"),
	std::make_tuple("GlobalAnalog", "ON_tot"),
	std::make_tuple("GlobalAnalog", "Rc"),
	std::make_tuple("GlobalAnalog", "Rf"),
	std::make_tuple("GlobalAnalog", "S_inv"),
	std::make_tuple("GlobalAnalog", "S_inv_buf"),
	std::make_tuple("GlobalAnalog", "S_noinv"),
	std::make_tuple("GlobalAnalog", "S_noinv_buf"),
	std::make_tuple("GlobalAnalog", "S_sk"),
	std::make_tuple("GlobalAnalog", "SelExtADC"),
	std::make_tuple("GlobalAnalog", "SelRisingEdge"),
	std::make_tuple("GlobalAnalog", "dac_pol"),
	std::make_tuple("GlobalAnalog", "gain_tot"),
	std::make_tuple("GlobalAnalog", "neg"),
	std::make_tuple("GlobalAnalog", "pol_trig_toa"),
	std::make_tuple("GlobalAnalog", "range_indac"),
	std::make_tuple("GlobalAnalog", "range_inv"),
	std::make_tuple("GlobalAnalog", "range_tot"),
	std::make_tuple("GlobalAnalog", "ref_adc"),
	std::make_tuple("GlobalAnalog", "trim_vbi_pa"),
	std::make_tuple("GlobalAnalog", "trim_vbo_pa"),
	std::make_tuple("DigitalHalf", "Adc_TH"),
	std::make_tuple("DigitalHalf", "Bx_offset"),
	std::make_tuple("DigitalHalf", "Bx_trigger"),
	std::make_tuple("DigitalHalf", "CalibrationSC"),
	std::make_tuple("DigitalHalf", "ClrAdcTot_trig"),
	std::make_tuple("DigitalHalf", "IdleFrame"),
	std::make_tuple("DigitalHalf", "L1Offset"),
	std::make_tuple("DigitalHalf", "MultFactor"),
	std::make_tuple("DigitalHalf", "SC_testRAM"),
	std::make_tuple("DigitalHalf", "SelTC4"),
	std::make_tuple("DigitalHalf", "Tot_P0"),
	std::make_tuple("DigitalHalf", "Tot_P1"),
	std::make_tuple("DigitalHalf", "Tot_P2"),
	std::make_tuple("DigitalHalf", "Tot_P3"),
	std::make_tuple("DigitalHalf", "Tot_P_Add"),
	std::make_tuple("DigitalHalf", "Tot_TH0"),
	std::make_tuple("DigitalHalf", "Tot_TH1"),
	std::make_tuple("DigitalHalf", "Tot_TH2"),
	std::make_tuple("DigitalHalf", "Tot_TH3"),
	std::make_tuple("DigitalHalf", "sc_testRAM"),
};

static std::array<std::tuple<std::string, std::string>, 42> roc_global_config = {
	std::make_tuple("Top", "BIAS_I_PLL_D"),
	std::make_tuple("Top", "DIV_PLL"),
	std::make_tuple("Top", "EN"),
	std::make_tuple("Top", "EN_HIGH_CAPA"),
	std::make_tuple("Top", "EN_LOCK_CONTROL"),
	std::make_tuple("Top", "EN_PLL"),
	std::make_tuple("Top", "EN_PhaseShift"),
	std::make_tuple("Top", "EN_RCG"),
	std::make_tuple("Top", "EN_REF_BG"),
	std::make_tuple("Top", "EN_probe_pll"),
	std::make_tuple("Top", "ENpE"),
	std::make_tuple("Top", "ERROR_LIMIT_SC"),
	std::make_tuple("Top", "EdgeSel_T1"),
	std::make_tuple("Top", "FOLLOWER_PLL_EN"),
	std::make_tuple("Top", "INIT_D"),
	std::make_tuple("Top", "INIT_DAC_EN"),
	std::make_tuple("Top", "Pll_Locked_sc"),
	std::make_tuple("Top", "PreL1AOffset"),
	std::make_tuple("Top", "RunL"),
	std::make_tuple("Top", "RunR"),
	std::make_tuple("Top", "S"),
	std::make_tuple("Top", "TestMode"),
	std::make_tuple("Top", "VOUT_INIT_EN"),
	std::make_tuple("Top", "VOUT_INIT_EXT_D"),
	std::make_tuple("Top", "VOUT_INIT_EXT_EN"),
	std::make_tuple("Top", "b_in"),
	std::make_tuple("Top", "b_out"),
	std::make_tuple("Top", "err_countR"),
	std::make_tuple("Top", "fc_error_count"),
	std::make_tuple("Top", "in_inv_cmd_rx"),
	std::make_tuple("Top", "lock_count"),
	std::make_tuple("Top", "n_counter_rst"),
	std::make_tuple("Top", "phase_ck"),
	std::make_tuple("Top", "phase_strobe"),
	std::make_tuple("Top", "rcg_gain"),
	std::make_tuple("Top", "sel_40M_ext"),
	std::make_tuple("Top", "sel_error"),
	std::make_tuple("Top", "sel_lock"),
	std::make_tuple("Top", "sel_strobe_ext"),
	std::make_tuple("Top", "srout"),
	std::make_tuple("Top", "statusL"),
	std::make_tuple("Top", "statusR"),
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

std::vector<std::string> filter_channel_columns(std::vector<std::string> columns);

std::vector<std::tuple<std::string, std::string>> filter_half_wise_columns(std::vector<std::string> columns);

std::vector<std::tuple<std::string, std::string>> filter_global_columns(std::vector<std::string> columns);


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

HalfWiseCacheKey calc_half_wise_key_summary_data(CacheKey row_key);
CacheKey calc_channel_cache_key_event_data(CacheKey row_key);
#endif
