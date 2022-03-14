#include <yaml-cpp/yaml.h>
#include <fstream>
#include <string>
#include <sstream>
#include <iostream>

// Read the string form a file
std::string read(const std::string& file_name) {
	std::ifstream file;
	file.exceptions (std::ifstream::failbit | std::ifstream::badbit);
	std::stringstream file_stream;
	try {
		file.open(file_name.c_str());
		file_stream << file.rdbuf();
		file.close();
	} catch (std::ifstream::failure e) {
		std::cout << "Error reading File: " << file_name << std::endl;
	}
	return file_stream.str();
}

int main() {
	YAML::Node lineup = YAML::Load("{1B: Prince Fielder, 2B: Rickie Weeks, LF: Ryan Braun}");
	for(YAML::const_iterator it=lineup.begin();it!=lineup.end();++it) {
	  std::cout << "Playing at " << it->first.as<std::string>() << " is " << it->second.as<std::string>() << "\n";
	}
}
