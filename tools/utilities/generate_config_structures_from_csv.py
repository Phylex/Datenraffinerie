import click
from jinja2 import Environment, FileSystemLoader
import pandas as pd


def count_bits(value):
    bits = 0
    for i in range(64):
        bits += (value >> i) & 1
    return bits


def get_block_count(data, block):
    return len(set(data.loc[data['SubBlock'] == block]['BlockID']))


def parse_block_types(data):
    blocks = {'global': [], 'half_wise': [], 'channel': []}
    for block in set(data['SubBlock']):
        block_data = data.loc[
                data['SubBlock'] == block]
        block_IDs = set(block_data['BlockID'])
        if len(block_IDs) == 1:
            blocks['global'].append(block)
        if len(block_IDs) == 2 and block != 'calib' and block != 'cm':
            blocks['half_wise'].append(block)
        if len(block_IDs) > 2 or block == 'calib' or block == 'cm':
            blocks['channel'].append(block)
    for k, val in blocks.items():
        if len(val) == 0:
            blocks[k] = None
    return blocks


def get_bits(data, block: str, param: str):
    regs = data.loc[data['SubBlock'] == block].loc[data['parameter'] == param]
    bits = 0
    for reg in regs.iterrows():
        reg = reg[1]
        bits = count_bits(reg['reg_mask'])
    return translate_to_hdf_data_type(bits)


def generate_yaml_lookup_key(data):
    lookup_table = {}
    for block in set(data['SubBlock']):
        block_params = list(set(data.loc[
            data['SubBlock'] == block].loc[
            data['BlockID'] == 0]['parameter']))
        prefix = ""
        if block == "HalfWise":
            prefix = "hw_"
        for param in block_params:
            instances = []
            for i in range(get_block_count(data, block)):
                instances.append({'block': block, 'id': i, 'param': param})
            if prefix + param in lookup_table:
                lookup_table[prefix + param] += instances
            else:
                lookup_table[prefix + param] = instances
    return lookup_table


def generate_column_data_type(data):
    lookup_table = {}
    for block in set(data['SubBlock']):
        block_data = data.loc[data['SubBlock'] == block]
        for param in set(block_data['parameter']):
            if block == "HalfWise":
                lookup_table['hw_' + param] = get_bits(data, block, param)
            else:
                lookup_table[param] = get_bits(data, block, param)
    return lookup_table


def translate_to_hdf_data_type(bit_length):
    if bit_length <= 8:
        return 'H5T_NATIVE_UCHAR'
    if bit_length <= 16:
        return "H5T_NATIVE_USHORT"
    if bit_length <= 32:
        return "H5T_NATIVE_INT"
    if bit_length <= 64:
        return "H5T_NATIVE_ULLONG"


@click.command()
@click.argument('register_description', type=click.Path(exists=True))
@click.argument('output', type=click.Path(exists=False))
def convert_to_code(register_description, output):
    env = Environment(
            loader=FileSystemLoader(searchpath="."),
            )
    code_template = env.get_template("code_struct_template.cpp")
    register_description = pd.read_csv(register_description)
    yaml_lookup_data = generate_yaml_lookup_key(register_description)
    column_data_type = generate_column_data_type(register_description)
    block_types = parse_block_types(register_description)
    rendered_template = code_template.render(lookup_table=yaml_lookup_data,
                                             coltype=column_data_type,
                                             block_types=block_types)
    with open(output, 'w') as f:
        f.write(rendered_template)


if __name__ == '__main__':
    convert_to_code()
