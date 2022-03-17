#include "yaml-tools.h"

void print_node_type(const YAML::Node& node) {
	switch (node.Type()) {
		case YAML::NodeType::Null:
			std::cout << "Node of Type Null" << std::endl;
			break;
		case YAML::NodeType::Scalar:
			std::cout << "Node of Type Scalar" << std::endl;
			break;
		case YAML::NodeType::Sequence:
			std::cout << "Node of Type Sequence" << std::endl;
			break;
		case YAML::NodeType::Map:
			std::cout << "Node of Type Map" << std::endl;
			break;
		case YAML::NodeType::Undefined:
			std::cout << "Node of Type Undefined" << std::endl;
			break;
	}
}

int main() {
	std::cout << "First Test" << std::endl;
	YAML::Node d1 = YAML::Load("{1B: Prince Fielder, 2B: Rickie Weeks, LF: Ryan Braun}");
	YAML::Node d2 = YAML::Load("{1B: Someone Else, 2B: Rickie Weeks, ALF: Ryan Braun}");
	YAML::Node diff = diff_dict<std::string>(d1, d2);
	std::cout << diff << std::endl;
	print_node_type(diff);

	std::cout << "\nSecond test" << std::endl;
	d1 = YAML::Load("{this: 1, that: 2, something: {else: 1}}");
	d2 = YAML::Load("{this: 2, that: 2, something: {else: 2}}");
	diff = diff_dict<int>(d1, d2);
	std::cout << diff << std::endl;
	print_node_type(diff);

	std::cout << "\nThird test" << std::endl;
	d1 = YAML::Load("{this: 1, that: 2, something: {else: 1}}");
	d2 = YAML::Load("{this: 2, that: 2, something: {else: 1}}");
	diff = diff_dict<int>(d1, d2);
	std::cout << diff << std::endl;
	print_node_type(diff);

	std::cout << "\nFourth test" << std::endl;
	d1 = YAML::Load("{this: 1, that: 2, something: [1, 1]}");
	d2 = YAML::Load("{this: 1, that: 2, something: [1, 2]}");
	diff = diff_dict<int>(d1, d2);
	std::cout << diff << std::endl;
	print_node_type(diff);

	std::cout << "\nFith test" << std::endl;
	d1 = YAML::Load("{this: 1, that: 2, something: [1, 2]}");
	d2 = YAML::Load("{this: 1, that: 2, something: [1, 2]}");
	diff = diff_dict<int>(d1, d2);
	std::cout << diff << std::endl;
	print_node_type(diff);

	std::cout << "\nUpdate Test 1" << std::endl;
	d1 = YAML::Load("{this: 1, that: 2, something: [1, 2]}");
	d2 = YAML::Load("{this: 2, that: 2, something: [1, 2]}");
	d1 = update<int>(d1, d2);
	std::cout << d1 << std::endl;

	std::cout << "\nUpdate Test 2" << std::endl;
	YAML::Node d13 = YAML::Load("{this: 1, that: 2, something: [1, 2]}");
	YAML::Node d14 = YAML::Load("{this: 2, that: 2, something: [{other: 3}, {that: 3}]}");
	d13 = update<int>(d13, d14);
	std::cout << d13 << std::endl;
	
	std::cout << "\nUpdate Test 3" << std::endl;
	d1 = YAML::LoadFile("../../tests/configuration/defaults/V3LDHexaboard-poweron-default.yaml");
	YAML::Node d3 = YAML::LoadFile("../../tests/configuration/defaults/V3LDHexaboard-poweron-default.yaml");
	d2 = YAML::LoadFile("../../tests/configuration/defaults/initLDV3.yaml");
	d1 = update<int>(d1, d2);
	diff = diff_dict<int>(d3, d1);
	std::cout << diff << std::endl;
	return 0;
}
