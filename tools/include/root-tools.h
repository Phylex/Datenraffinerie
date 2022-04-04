#ifndef _ROOT_TOOLS_H_
#define _ROOT_TOOLS_H_
#include <TFile.h>
#include <TTree.h>
#include <vector>
#include <iostream>
#include <string>
std::vector<std::string> filter_measurement_columns(bool event_mode, std::vector<std::string> columns);
TTree *openRootTree(std::string root_file_path);
#endif
