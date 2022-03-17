#ifndef _YAML_TOOL_H_
#define _YAML_TOOL_H_

#include <yaml-cpp/yaml.h>
#include <fstream>
#include <string>
#include <sstream>
#include <iostream>

template<typename T>
YAML::Node diff_dict(const YAML::Node&, const YAML::Node&);

template<typename ValType>
YAML::Node diff_sequence(const YAML::Node &d1, const YAML::Node &d2);

template<typename ValType>
YAML::Node update(YAML::Node d1, const YAML::Node &d2);

template<typename ValType>
YAML::Node update_map(YAML::Node d1, const YAML::Node &d2);

template<typename ValType>
YAML::Node update_sequence(YAML::Node d1, const YAML::Node &d2);

template<typename ValType>
YAML::Node update(YAML::Node d1, const YAML::Node &d2) {
	if (d1.Type() != d2.Type())
		return d1;
	switch (d1.Type()) {
		case YAML::NodeType::Sequence:
			d1 = update_sequence<ValType>(d1, d2);
			break;
		case YAML::NodeType::Map:
			d1 = update_map<ValType>(d1, d2);
			break;
		case YAML::NodeType::Scalar:
			if (d1.as<ValType>() != d2.as<ValType>()) {
				d1 = d2;
			}
			break;
		default:
			break;
	}
	return d1;
}

template<typename ValType>
YAML::Node update_map(YAML::Node d1, const YAML::Node &d2) {
	for (YAML::const_iterator d2_node=d2.begin(); d2_node!=d2.end(); d2_node++) {
		if (d1[d2_node->first.as<std::string>()]) {
			if (d1[d2_node->first.as<std::string>()].Type() == d2_node->second.Type()) {
				switch (d1[d2_node->first.as<std::string>()].Type()) {
					case YAML::NodeType::Map:
						d1[d2_node->first.as<std::string>()] = update_map<ValType>(d1[d2_node->first.as<std::string>()], d2_node->second);
						break;
					case YAML::NodeType::Sequence:
						d1[d2_node->first.as<std::string>()] = update_sequence<ValType>(d1[d2_node->first.as<std::string>()], d2_node->second);
						break;
					case YAML::NodeType::Scalar:
						if (d1[d2_node->first.as<std::string>()].as<ValType>() != d2_node->second.as<ValType>()) {
							d1[d2_node->first.as<std::string>()] = d2_node->second;
						}
						break;
					default:
						break;
				}
			} else if (d2_node->second.Type() != YAML::NodeType::Null) {
				d1[d2_node->first.as<std::string>()] = d2_node->second;
			}
		} else {
			d1[d2_node->first.as<std::string>()] = d2_node->second;
		}
	}
	return d1;
}

template<typename ValType>
YAML::Node update_sequence(YAML::Node d1, const YAML::Node &d2) {
	size_t delta = d1.size() - d2.size();
	size_t max_common_index;
	if (delta >= 0) {
		max_common_index = d1.size() - delta;
	} else {
		max_common_index = d1.size();
	}
	for (size_t i = 0; i < max_common_index; i++) {
		if (d1[i].Type() == d2[i].Type()) {
			switch (d1[i].Type()) {
				case YAML::NodeType::Scalar:
					if (d1[i].as<ValType>() != d2[i].as<ValType>()) {
						d1[i] = d2[i];
					}
					break;
				case YAML::NodeType::Map:
					d1[i] = update_map<ValType>(d1[i], d2[i]);
					break;
				case YAML::NodeType::Sequence:
					d1[i] = update_sequence<ValType>(d1[i], d2[i]);
				default:
					break;
			}
			if (d1[i].as<ValType>() != d2[i].as<ValType>()) {
				d1[i] = d2[i];
			}
		} else if (d2[i].Type() != YAML::NodeType::Null) {
			d1[i] = d2[i];
		}
	}
	// d2 is longer than d1, so append all the elements of d2 to d1
	if (delta < 0) {
		for (size_t i = max_common_index; i < max_common_index - delta; i++) {
			d1.push_back(d2[i]);
		}
	}
	return d1;
}

template<typename ValType>
YAML::Node diff_sequence(const YAML::Node &d1, const YAML::Node &d2) {
	YAML::Node diff;
	if (d1.size() != d2.size()) {
		diff = d2;
		return diff;
	}
	bool sequence_matches = true;
	for (std::size_t i = 0; i < d1.size(); i++) {
		if (d1[i].Type() == d2[i].Type()) {
			switch (d1[i].Type()) {
				case YAML::NodeType::Map:
					diff = diff_dict<ValType>(d1[i], d2[i]);
					if (diff.Type() != YAML::NodeType::Null) {
						sequence_matches = false;
					}
					break;
				case YAML::NodeType::Scalar:
					if (d1[i].as<ValType>() != d2[i].as<ValType>()) {
						sequence_matches = false;
					}
					break;
				default:
					break;
			}
		}
	}
	if (sequence_matches) {
		return diff;
	} else {
		diff = d2;
		return diff;
	}
}

template<typename ValType>
YAML::Node diff_dict(const YAML::Node &root, const YAML::Node &comp) {
	YAML::Node diff;
	for (YAML::const_iterator cnode=comp.begin(); cnode!=comp.end(); cnode++) {
		bool found_match = false;
		YAML::Node potential_diff;
		for (YAML::const_iterator rnode=root.begin(); rnode!=root.end(); rnode++) {
			if (rnode->first.as<std::string>() == cnode->first.as<std::string>()) {
				if (rnode->second.Type() == cnode->second.Type()) {
					switch (rnode->second.Type()) {
						case YAML::NodeType::Map:
							potential_diff = diff_dict<ValType>(rnode->second, cnode->second);
							if (potential_diff.Type() == YAML::NodeType::Null) {
								found_match = true;
							}
							break;
						case YAML::NodeType::Sequence:
							potential_diff = diff_sequence<ValType>(rnode->second, cnode->second);
							if (potential_diff.Type() == YAML::NodeType::Null)
								found_match = true;
							break;
						case YAML::NodeType::Scalar:
							if (rnode->second.as<ValType>() == cnode->second.as<ValType>())
								found_match = true;
							break;
						default:
							break;
					}
				}
				break;
			}
		}
		if (!found_match && potential_diff.Type() == YAML::NodeType::Null) {
			diff[cnode->first.as<std::string>()] = cnode->second.as<ValType>();
		} else if (!found_match && potential_diff.Type() != YAML::NodeType::Null) {
			diff[cnode->first.as<std::string>()] = potential_diff;
		}
	}
	return diff;
}
#endif
