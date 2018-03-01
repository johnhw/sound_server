import os
package_directory = os.path.dirname(os.path.abspath(__file__))
from openal import *
from ctypes import *

import regex

types =  {"ALint64SOFT": ctypes.c_int64,
"ALboolean": ctypes.c_bool,
"ALchar": ctypes.c_char,
"ALbyte":ctypes.c_byte,
"ALubyte":ctypes.c_ubyte,
"ALshort":ctypes.c_int16,
"ALushort":ctypes.c_uint16,
"ALint":ctypes.c_int32,
"ALuint":ctypes.c_uint32,
"ALsizei":ctypes.c_int32,
"ALenum":ctypes.c_int32,
"ALfloat":ctypes.c_float,
"ALdouble":ctypes.c_double}



def get_real_type(type_string):
    type_string = type_string.strip()
    if "LP" in type_string or type_string=="void *":
        return c_void_p
    if type_string=="void" or type_string=="ALvoid":
        return None
    if type_string.startswith("const "):
        return get_real_type(type_string[6:])
    if type_string[-1]=='*':
        return POINTER(get_real_type(type_string[:-1]))
    return types[type_string]


def parse_definitions(fname):
    defs = {}
    procs = []
    
    with open(os.path.join(package_directory, fname)) as f:
        for line in f:            
            if "/*" not in line:
                # parse #define CONSTANT xxx
                # xxx can be
                # Hex: 0xdeadbeef
                # Integer: 20
                # float: 0.2f
                # string: "string"
                # boolean: AL_TRUE or AL_FALSE
                if "#define" in line:
                    matches = (regex.findall( r"#define\s*(\w*)\s*(\S*).*", line))
                    for name, value in matches:
                        if len(value)>2 and value[0]=='(' and value[-1]==')':
                            value = value[1:-1]
                        if value=='AL_TRUE':
                            value = 1
                        elif value=='AL_FALSE':
                            value = 0
                        elif value.endswith("f"):
                            value = float(value[:-1])
                        elif value.startswith("0x"):
                            value = int(value[2:], base=16)
                        elif value.startswith('"'):
                            value = value[1:-1]
                        elif regex.match("\-?\d+", value):
                            value = int(value)
                        defs[name] = value

                # match API calls
                # AL_API call_name AL_APIENTRY (type paramname, type paramname, ...)
                if "AL_API" in line:
                    matches = regex.match("AL_API (.*) AL_APIENTRY (\w*)\(((const )?(\w+ \*?)(\w+),?\s*)*\)\;", line)
                    if matches:
                        res_name = matches.captures(1)[0]
                        name = matches.captures(2)[0]
                        params = matches.captures(6)
                        type_names = matches.captures(5) 

                        if res_name=='ALvoid' or res_name == 'void':
                            res_type = None
                        else:
                            res_type = get_real_type(res_name)                        
                        arg_types = [get_real_type(t) for t in type_names]
                        procs.append({"res_type":res_type, "name":name, "arg_types":arg_types, "params":params, "type_names":type_names, "res_name":res_name})            
    return defs, procs



def get_proc(proc):
    name = proc["name"]
    res_type = proc["res_type"]
    arg_types = proc["arg_types"]
    params = proc["params"]
    type_names = proc["type_names"]

    proc_addr = alGetProcAddress(c_char_p(bytes(name, encoding="ASCII")))    
    # create a wrapper function that executes the call, and then
    # forces an error check
    def fn(*args, **kwargs):    
        fn_type = CFUNCTYPE(res_type, *arg_types)(proc_addr)    
        ret = fn_type(*args)        
        al_check_error(ret, None, None)
    
    # create docstrings which reflect the original lines defining the functions
    arg_names = ", ".join(["%s %s" % (type_names[i], params[i]) for i in range(len(params))])
    fn.__doc__ = "%s %s(%s);" % (proc["res_name"], proc["name"], arg_names)
    
    return fn

def add_procs(procs, d):
    for proc in procs:        
        name = proc["name"]
        d[name] = get_proc(proc)

class Namespace:
    def __init__(self, kwargs):
        self.__dict__.update(kwargs)


def load_extensions():
    all_defs = {}    
    enums = {}
    for header in ["openal_headers/efx.h", "openal_headers/alext.h", "openal_headers/al.h", "openal_headers/alc.h"]:
        try:
            defs, procs = parse_definitions(header)        
            all_defs.update(defs)
            for k,v in defs.items():
                enums[v] = k
            add_procs(procs, all_defs)
        except FileNotFoundError:
            print("Header file %s does not exist; Download the OpenAL header files from https://github.com/kcat/openal-soft/tree/master/include/AL and copy to openal/")                
    all_defs["openal_enums"] = enums
    return Namespace(all_defs)
