#ifndef _ROCV3_CONFIG_STRUCT_H_
#define _ROCV3_CONFIG_STRUCT_H_
#include <array>
#include <tuple>
#include <vector>
#include <string>
#include <hdf5.h>
#include <map>


static std::map<std::string, hid_t> column_type {
{% for col, type in coltype|items %}  {"{{ col }}", {{ type }}},
{% endfor %}};

{% for type, blocks in block_types|items %}static const std::array<std::string, {{ blocks|length }}> {{ type }} = {
{% for elem in blocks %}  "{{ elem }}",
{% endfor %}};

{% endfor %}
static const std::map<std::string, std::vector<std::tuple<std::string, int, std::string>>> generate_roc_config_key_lookup() {
  std::map<std::string, std::vector<std::tuple<std::string, int, std::string>>> key_lookup;
  std::vector<std::tuple<std::string, int, std::string>> key_entry;
{% for col_name, block in lookup_table|items %}{% for instance in block %}  key_entry.push_back(std::make_tuple("{{ instance.block }}", {{ instance.id }}, "{{ instance.param }}"));
{% endfor %}  key_lookup.insert({"{{ col_name }}", key_entry});
  key_entry.clear();
{% endfor %}  return key_lookup;
};

static const std::map<std::string, std::vector<std::tuple<std::string, int, std::string>>> roc_config_key = generate_roc_config_key_lookup();
#endif
