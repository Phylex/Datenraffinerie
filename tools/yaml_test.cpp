#include <yaml-cpp/yaml.h>
#include <fstream>
#include <string>
#include <sstream>
#include <iostream>

template<typename T>
YAML::Node diff_dict(const YAML::Node&, const YAML::Node&);

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
			}
		}
	}
	if (sequence_matches) {
		return diff;
	} else {
		return d2;
	}
}

template<typename ValType>
YAML::Node diff_dict(const YAML::Node &root, const YAML::Node &comp) {
	YAML::Node diff;
	// for key2 in d2.items()
	for (YAML::const_iterator cnode=comp.begin(); cnode!=comp.end(); cnode++) {
		// if key2 not in d1.keys()
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


int main() {
	std::cout << "First Test" << std::endl;
	YAML::Node d1 = YAML::Load("{1B: Prince Fielder, 2B: Rickie Weeks, LF: Ryan Braun}");
	YAML::Node d2 = YAML::Load("{1B: Someone Else, 2B: Rickie Weeks, LF: Ryan Braun}");
	YAML::Node diff = diff_dict<std::string>(d1, d2);
	std::cout << diff << std::endl;
	std::cout << "\nSecond test" << std::endl;
	YAML::Node d3 = YAML::Load("{this: 1, that: 2, something: {else: 1}}");
	YAML::Node d4 = YAML::Load("{this: 2, that: 2, something: {else: 2}}");
	YAML::Node diff2 = diff_dict<int>(d3, d4);
	std::cout << diff2 << std::endl;
	std::cout << "\nThird test" << std::endl;
	YAML::Node d5 = YAML::Load("{this: 1, that: 2, something: {else: 1}}");
	YAML::Node d6 = YAML::Load("{this: 2, that: 2, something: {else: 1}}");
	YAML::Node diff3 = diff_dict<int>(d5, d6);
	std::cout << diff3 << std::endl;
	std::cout << "\nFourth test" << std::endl;
	YAML::Node d7 = YAML::Load("{this: 1, that: 2, something: [1, 1]}");
	YAML::Node d8 = YAML::Load("{this: 1, that: 2, something: [1, 2]}");
	YAML::Node diff4 = diff_dict<int>(d7, d8);
	std::cout << diff4 << std::endl;
	return 0;
}
