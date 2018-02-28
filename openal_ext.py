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
    
    with open(fname) as f:
        for line in f:            
            if "/*" not in line:
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
                if "AL_API" in line:
                    matches = regex.match("AL_API (.*) AL_APIENTRY (\w*)\(((const )?(\w+ \*?)(\w+),?\s*)*\)\;", line)
                    if matches:
                        res_type = matches.captures(1)[0]
                        name = matches.captures(2)[0]
                        types = matches.captures(5) 
                        if res_type=='ALvoid' or res_type == 'void':
                            res_type = None
                        else:
                            res_type = get_real_type(res_type)
                        types = [get_real_type(t) for t in types]
                        procs.append((res_type, name, types))            
    return defs, procs



def get_proc(name, res_type, *arg_types):
    proc = alGetProcAddress(c_char_p(bytes(name, encoding="ASCII")))    
    
    def fn(*args, **kwargs):    
        fn_type = CFUNCTYPE(res_type, *arg_types)(proc)    
        ret = fn_type(*args)
        
        al_check_error(ret, None, None)
    return fn

def add_procs(procs, d):
    for proc in procs:        
        res, name, args = proc        
        d[name] = get_proc(name, res, *args)

class Namespace:
    def __init__(self, kwargs):
        self.__dict__.update(kwargs)

def load_extensions():
    all_defs = {}    
    for header in ["openal/efx.h", "openal/alext.h"]:
        defs, procs = parse_definitions(header)
        all_defs.update(defs)
        add_procs(procs, all_defs)
    return Namespace(all_defs)