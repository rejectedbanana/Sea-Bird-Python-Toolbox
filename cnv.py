"""
Functions that import Sea-Bird cnv files as dictionaries
"""
import os
import json
import re
import sys
import numpy as np  # type: ignore
import requests # type: ignore

"""
Load the JSON dictionary that is used to convert Sea-Bird variables
to the appropriate formats
"""
datadir = os.path.dirname(__file__)
filename = "sbs_variables.json"
targetfile = os.path.join(datadir, filename)
# with open(targetfile, "r") as file:
#     data = json.load(file)


def load_variable_dictionary(target_file):
    with open(targetfile, "r") as file:
        variable_dictionary = json.load(file)
    return variable_dictionary

data = load_variable_dictionary(targetfile)


# make the function to input the JSON information
def rename_sbs_variable(sbs_variable):
    """
    Given an sbs_var string, return kvar_name, kvar_format, and kvar_units.

    :param sbs_var_input: The variable name to search for in sbs_var list
    :return: Tuple of (name, format, units) or None if not found
    """
    for entry in data:
        if sbs_variable in entry["sbs_variable"]:
            return entry["kname"], entry["kformat"], entry["kunits"]
    return None  # Return None if not found


def is_xml_line(line):
    """
    Detect if a line is formatted as XML.
    
    I've included using "/>" to detect xml, because there are 
    some misplaced carriage returns within tags in the output
    from SBE 56 temperature sensors. 
    """
    return bool(re.search(r'<.*?>', line)) or bool(re.search(r'/>\s*$', line))

# make the function to read the SBS CNV
def read(target_file):
    s = {
        'source': target_file,
        'DataFileType': None,
        'SeasaveVersion': None,
        'instrumentheaders': {},
        'userheaders': {},
        'softwareheaders': {},
        'vars': [],
        'longname': [],
        'units': [],
        'span': [],
        'kvars': [],
        'kvars_format': [], 
        'data': {}  # Dictionary to store data columns
    }

    # Download file if URL
    if target_file.startswith(('http://', 'https://')):
        response = requests.get(target_file) 
        response.raise_for_status()
        file_content = response.text.splitlines()
    else:
        with open(target_file, 'r') as file:
            file_content = file.readlines()

    nheader = 0
    data_lines = []
    header_done = False  # Flag to detect the start of data

    # go through the header line by line because the output varies with each instrument
    for line in file_content:
        line = line.strip()

        # Skip lines that are formatted as XML
        if is_xml_line(line):
            # print(line)
            continue

        # Detect end of headers and start collecting data
        if line.startswith('*END*'):
            header_done = True
            continue

        if not header_done:
            # Process header lines
            nheader += 1

            # when you've reached the end of the header, break the loop
            if line.startswith('*END*'):
                break

            elif line.startswith('* '):
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = re.sub(r'\W', '_', key.strip())
                    s['instrumentheaders'][key] = value.strip()
                elif 'Data File' in line:
                    s['DataFileType'] = line[3:].strip()
                elif 'Seasave' in line:
                    s['SeasaveVersion'] = line[3:].strip()

            elif line.startswith('**'):
                key = re.sub(r'\W', '_', line.split(':', 1)[0][3:].strip())
                value = ':'.join(line.split(':')[1:]).strip()
                s['userheaders'][key] = value

            elif line.startswith('# '):
                if '# name' in line:
                    var_num = int(re.search(r'# name (\d+)', line).group(1))
                    var_name = re.search(r'= ([^:]+)', line).group(1).strip()
                    long_name = re.search(r': ([^[]+)', line).group(1).strip()
                    unit_match = re.search(r'\[(.+?)\]', line)
                    units = unit_match.group(1) if unit_match else ''
                    s['vars'].append(var_name)
                    s['longname'].append(long_name)
                    s['units'].append(units)
                elif '# span' in line:
                    # span_values = list(map(float, re.findall(r'[-+]?\d*\.\d+|\d+', line)))
                    span_values = line.split()
                    s['span'].append(span_values[-2:])
                elif '=' in line:
                    key, value = line.split('=', 1)
                    s['softwareheaders'][key.strip()] = value.strip()

        else: 
            # Collect data lines after *END*
            data_lines.append(line)

    # Normalize variable names
    for var in s['vars']:
        mvar, mvar_format, _ = rename_sbs_variable(var)
        s['kvars'].append(mvar)
        s['kvars_format'].append(mvar_format)

    # Convert data lines into NumPy arrays
    if data_lines:
        data_array = np.loadtxt(data_lines)  # Convert data to NumPy array
        for i, mvar in enumerate(s['kvars']):
            s['data'][mvar] = data_array[:, i]  # Assign each column to corresponding variable

    return s
