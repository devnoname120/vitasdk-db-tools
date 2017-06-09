#!/usr/bin/env python3

from dbtools import *

import ruamel.yaml as yaml
import subprocess
import string

from glob import glob
from sys import argv


class HexWInt(yaml.scalarint.ScalarInt):
    def __new__(cls, value, width):
        x = yaml.scalarint.ScalarInt.__new__(cls, value)
        x._width = width   # keep the original width
        return x


def alt_construct_yaml_int(constructor, node):
    # check for 0x0 starting hex integers
    value_s = yaml.compat.to_str(constructor.construct_scalar(node))
    if not value_s.startswith('0x0'):
        return constructor.construct_yaml_int(node)
    return HexWInt(int(value_s[2:], 16), len(value_s[2:]))

yaml.constructor.RoundTripConstructor.add_constructor(
    u'tag:yaml.org,2002:int', alt_construct_yaml_int)

def represent_hexw_int(representer, data):
    return representer.represent_scalar(u'tag:yaml.org,2002:int',
                                        '0x{:0{}X}'.format(data, data._width))

yaml.representer.RoundTripRepresenter.add_representer(
    HexWInt, represent_hexw_int)

nids = {}

db_lookup = NIDDatabase()

compact_exports = open("compact_exports.txt")

module = None
library = None
library_name = ""
for line in compact_exports:
    if line == "" or str.isspace(line):
        continue
    splt = line.split(" ")
    
    keyword = splt[0]
    if keyword == "module":
        name, nid = splt[1], int(splt[2], 0)
        module = db_lookup.addModule(name, nid)
    elif keyword == "library":
        library_name, syscall, nid = splt[1], splt[2], int(splt[3], 0)
        syscall = True if syscall == "yes" else False

        library = db_lookup.addLibrary(module, library_name, nid)
        
        if not syscall and db_lookup.soundsKernel(library_name):
            db_lookup.setLibraryKernel(library, True)
        else:
            db_lookup.setLibraryKernel(library, False)
    elif keyword == "function":
        nid = int(splt[1], 0)
        name = library_name + "_" + hex(nid)[2:].upper().zfill(8)
        db_lookup.addFunction(library, name, nid)

db_lookup.removeModule("taihen")
db_lookup.removeModule("vita_dump")

db_lookup.save("db_lookup.yml", True)

