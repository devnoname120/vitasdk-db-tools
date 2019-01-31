#!/usr/bin/env python3

import ruamel.yaml as yaml
import subprocess
import string
import regex as re

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
        yaml.allow_duplicate_keys = True
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
    
    def mergeList(self, nids_lookup, nids_txt):
        fnids_txt = open(nids_txt)
        for entry in fnids_txt:
            tpl = tuple(filter(None, re.split(r"\s", entry)))
            if len(tpl) != 2:
                print("[warning] Ignoring entry", entry, "because it's not a valid 'nid name'")
                continue

            nid, function_name = tpl
            nid = int(nid, 0)

            try:
                moduleName, module, libraryName, library, functionName = nids_lookup.findFunctionByNid(nid)
            except IndexError:
                print("[error] Function", function_name, "with NID", '0x{:08X}'.format(nid), "not found in lookup, ignoring...")
                continue

            try:
                dbModuleName, dbModule, dbLibraryName, dbLibrary, dbFunctionName = self.findFunctionByNid(nid)

                # Ignore k prefix and ForUser suffix differences
                if dbFunctionName != function_name and dbFunctionName != "k" + function_name and dbFunctionName + "ForUser" != function_name:
                    print("[warning] Function", function_name, "found with different name in db:", dbFunctionName, ", skipping...")
                continue
            except IndexError:
                pass


            db_library = None
            for cLibraryName, cLibrary in self.findLibraryByNid(library['nid']):
                assert db_library is None # There should be only one corresponding library
                db_library = cLibrary

            if db_library is None:
                db_module = None
                for cModuleName, cModule in self.findModule(module):
                    assert db_module is None  # There should be only one corresponding module
                    db_module = cModule

                if db_module is not None:
                    newLib = self.addLibrary(db_module, libraryName, library['nid'])
                    self.setLibraryKernel(newLib, library["kernel"])

                    self.addFunctionWithPrefixSuffix(newLib, function_name, nid)
                else:
                    newModule = self.addModule(moduleName, module['nid'])
                    newLib = self.addLibrary(newModule, libraryName, library['nid'])
                    self.setLibraryKernel(newLib, library["kernel"])

                    self.addFunctionWithPrefixSuffix(newLib, function_name, nid)
            else:
                self.addFunctionWithPrefixSuffix(db_library, function_name, nid)


            # Commented this because I don't know what it's used for
            # libraryName = re.sub('User$', '', libraryName)

            

    def setModuleNid(self, module, nid):
        #for _, cModule in self.findModule(module):
        module["nid"] = HexWInt(nid, 8)
    
    def setLibraryNid(self, library, nid, module=None):
        #for _, cLibrary in self.findLibrary(library, module):
        library["nid"] = HexWInt(nid, 8)

    def setLibraryKernel(self, library, kernel):
        library["kernel"] = kernel
    
    def soundsKernel(self, library):
        if library.endswith(("ForKernel", "ForDriver")):
            return True
        return False

    def addModule(self, name, nid):
        if not self.nids["modules"]:
            self.nids["modules"] = {}

        try:
            self.nids["modules"][name]
        except:
            self.nids["modules"][name] = {}

            self.nids["modules"][name]["nid"] = nid
        return self.nids["modules"][name]

    def removeModule(self, module_name):
        for modu in self.findModule(module_name):
            try:
                self.nids["modules"].pop(module_name)
            except:
                pass
            return

    def addLibrary(self, module, name, nid):
        # db.yml never has a User suffix
        # name = re.sub('User$', '', name)

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

    def addFunctionWithPrefixSuffix(self, library, name, nid):
        if library["kernel"] == True:
            if not name.startswith("sce"):
                print("[warning] Setting k prefix to function with unknown prefix:", name)
            name = "k" + name
        if name.endswith("ForKernel") or name.endswith("ForDriver"):
            if library["kernel"] != True:
                print("[error] Function", name, "has a kernel prefix but is not in a library marked kernel")
            name = name[:-len("ForKernel")] # Remove suffix

        self.addFunction(library, name, nid)

    def addFunction(self, library, name, nid):
        try:
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
        if modules is None:
            return

        for cModule in modules:
            yield (cModule, modules[cModule])

    def libraries(self, module=None):
        
        if module is not None:
            if not "libraries" in module or module["libraries"] is None:
                return # this module has no libraries, it's ok

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
            # User libraries are suffixed with 'User' but this suffix is not in db.yml
            if cLibraryName == library or cLibraryName == library + "User" :
                yield (cLibraryName, cLibrary)

    def findLibraryByNid(self, nid):
        for cModuleName, cModule in self.modules():
            for cLibraryName, cLibrary in self.libraries(cModule):
                # User libraries are suffixed with 'User' but this suffix is not in db.yml
                if cLibrary['nid'] == nid :
                    yield (cLibraryName, cLibrary)

    def findFunctionByNid(self, nid):
        for cModuleName, cModule in self.modules():
            for cLibraryName, cLibrary in self.libraries(cModule):
                if not "functions" in cLibrary or cLibrary["functions"] is None:
                    continue # This library has no functions

                funcs = cLibrary["functions"]
                for func in funcs:
                    if funcs[func] == nid:
                        return cModuleName, cModule, cLibraryName, cLibrary, func
        raise IndexError("Not found")
                    
if __name__ == "__main__":
    if argv[1] == "fixnids":
        db = NIDDatabase("db.yml")
        db_lookup = NIDDatabase("db_lookup.yml")

        db.fixNids(db_lookup)
        db.save("dbfixed.yml")

    elif argv[1] == "mergenids":
        db = NIDDatabase("db.yml")
        db_lookup = NIDDatabase("db_lookup.yml")

        db.mergeList(db_lookup, "nids.txt")
        db.save("dbmerged.yml")

