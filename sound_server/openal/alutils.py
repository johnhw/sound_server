from openal import *
from openal._al import *
from openal._alc import *
from . import openal_ext
from ctypes import *
import ctypes

def attr_list(d):
    # convert a dictionary of enum:value pairs into an attribute list
    l = [item for pair in zip(d.keys(), d.values()) for item in pair]    
    attr_list = (ALint * (len(l)+1))()
    for i in range(len(l)):
        attr_list[i] = l[i]
    attr_list[len(l)] = 0
    return attr_list

def cstr(s):
    return c_char_p(bytes(s, encoding="ASCII"))

def has_extension(ext):
    return alcIsExtensionPresent(oalGetDevice(), cstr(ext))

def has_efx():
    return has_extension("ALC_EXT_EFX")

def get_enum(s):
    return alGetEnumValue(cstr(s))

def get_device_attributes():
    # get size of buffer
    attr_size = (ALint * 1)()
    alcGetIntegerv(oalGetDevice(), ALC_ATTRIBUTES_SIZE, 4, attr_size)
    # read entire buffer
    attrs = (ALint * attr_size[0])()
    alcGetIntegerv(oalGetDevice(), ALC_ALL_ATTRIBUTES, attr_size[0], attrs)
    # convert to enum name dictionary
    attributes = {}
    for a in range(attr_size[0]//2):
        attributes[openal_enums[attrs[a*2]]] = attrs[a*2+1]        
    return attributes

ext = None
def init():
    global ext
    ext  = openal_ext.load_extensions().__dict__
    globals().update(ext)  # essentially import *