#!/usr/bin/env python3

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


class NIDDatabase:
    def __init__(self, fnids_db=None):
        if isinstance(fnids_db, str):
            self.load(fnids_db)
        else:
            self.nids = {}
            self.nids["version"] = 2
            self.nids["firmware"] = 3.60
            self.nids["modules"] = {}
    def load(self, nids_db):
        fnids_db = open(nids_db)
        self.nids = yaml.round_trip_load(fnids_db)
        fnids_db.close()
    
    def save(self, nids_db, no_inline=True):
        fnids_db = open(nids_db, "w")
        yaml.dump(self.nids, fnids_db, Dumper=yaml.RoundTripDumper, default_flow_style=False)
        fnids_db.close()

    def fixNids(self, nids_lookup):
        for cModuleName, cModule in self.modules():
            for lModuleName, lModule in nids_lookup.findModule(cModuleName):
                print("Change module nid {} to {}".format(cModule["nid"], lModule["nid"])) 
                self.setModuleNid(cModule, lModule["nid"])

        for cLibraryName, cLibrary in self.libraries():
            for lLibraryName, lLibrary in nids_lookup.findLibrary(cLibraryName):
                self.setLibraryNid(cLibrary, lLibrary["nid"])

    def setModuleNid(self, module, nid):
        #for _, cModule in self.findModule(module):
        module["nid"] = HexWInt(nid, 8)
    
    def setLibraryNid(self, library, nid, module=None):
        #for _, cLibrary in self.findLibrary(library, module):
        library["nid"] = HexWInt(nid, 8)

    def setLibraryKernel(self, library, kernel):
        library["kernel"] = kernel

    def addModule(self, name, nid):
        try:
            setModuleNid(name, nid)
            return mod
        except:
            if not self.nids["modules"]:
                self.nids["modules"] = {}

            try:
                self.nids["modules"][name]
            except:
                self.nids["modules"][name] = {}

            self.setModuleNid(self.nids["modules"][name], nid)
            return self.nids["modules"][name]

    def removeModule(self, module_name):
        for modu in self.findModule(module_name):
            try:
                self.nids["modules"].pop(module_name)
            except:
                pass
            return

    def addLibrary(self, module, name, nid):
        try:
            self.findLibrary(name, module) # Does not raise exception if library already exists
            setLibraryNid(name, nid, module)
            return lib
        except:
            try:
                module["libraries"]
            except:
                module["libraries"] = {}
            
            try:
                module["libraries"][name]
            except:
                module["libraries"][name] = {}

            module["libraries"][name]["nid"] = HexWInt(nid, 8)
            return module["libraries"][name]

    def addFunction(self, library, name, nid):
        try:
            library[name] #for lib in self.findFunction(name, module): # Function already exists
            library[name] = HexWInt(nid)
            return library[name]
        except:
            try:
                library["functions"]
            except:
                library["functions"] = {}
            
            library["functions"][name] = HexWInt(nid, 8)
            return library["functions"][name]

    def modules(self):
        modules = self.nids["modules"]
        for cModule in modules:
            yield (cModule, modules[cModule])

    def libraries(self, module=None):
        
        if module != None:
            libraries = module["libraries"]
            for cLibrary in libraries:
                yield (cLibrary, libraries[cLibrary])
        else:
            for _, cModule in self.modules():
                try:
                    libraries = cModule["libraries"]
                except:
                    cModule["libraries"] = {}
                    libraries = cModule["libraries"]
                for cLibrary in libraries:
                    yield (cLibrary, libraries[cLibrary]) 


    def findModule(self, module):
        for cModuleName, cModule in self.modules():
            if cModuleName == module:
                yield (cModuleName, cModule)

    def findLibrary(self, library, module=None):
        for cLibraryName, cLibrary in self.libraries(module):
            if cLibraryName == library:
                yield (cLibraryName, cLibrary)
if __name__ == "__main__":
    if argv[1] == "fixnids":
        db = NIDDatabase("db.yml")
        db_lookup = NIDDatabase("db_lookup.yml")

        db.fixNids(db_lookup)
        db.save("dbfixed.yml")

