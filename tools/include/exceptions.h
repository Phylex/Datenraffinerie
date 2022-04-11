#include <exception>
#include <stdexcept>

class PandasFormatException: public std::exception {
public:
	PandasFormatException() {};
	virtual const char* what() const throw() {
		return "Format of the file in conflict with the format specified by pandas:\n";
	}
};

