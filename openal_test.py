import os
os.environ["ALSOFT_LOGLEVEL"] = "3"
os.environ["ALSOFT_LOGFILE"] = "openal.log"
os.environ["ALSOFT_CONF"] = "openal.cfg"

from openal import *
from openal._al import *
from openal._alc import *
from ctypes import *
import time
import ctypes
import openal_ext

ALC_DEFAULT_ALL_DEVICES_SPECIFIER=0x1012
ALC_ALL_DEVICES_SPECIFIER=0x1013
if __name__=="__main__":
    
    wav = oalOpen("test/creature_1.wav")
    devices = alcGetString(None, ALC_ALL_DEVICES_SPECIFIER)
    print(devices)

    ext = openal_ext.load_extensions()
    globals().update(ext.__dict__)

    if not alcIsExtensionPresent(alcGetContextsDevice(alcGetCurrentContext()), c_char_p(b"ALC_EXT_EFX")):
        print("No EFX unit")

    
    has_eax = alGetEnumValue(c_char_p(b"AL_EFFECT_EAXREVERB"))
    if has_eax!=0:
        efx = ALuint()
        alGenEffects(1, byref(efx))
        alEffecti(efx, AL_EFFECT_TYPE, AL_EFFECT_EAXREVERB)
        alEffectf(efx, AL_EAXREVERB_DENSITY, 1.0)
        alEffectf(efx,  AL_EAXREVERB_DIFFUSION, 1.0)
        alEffectf(efx,  AL_EAXREVERB_GAIN, 1.0)
        alEffectf(efx,  AL_EAXREVERB_GAINHF, 0.891)
        alEffectf(efx,  AL_EAXREVERB_GAINLF, 1.0)
        alEffectf(efx,  AL_EAXREVERB_DECAY_TIME, 2.49)
        alEffectf(efx,  AL_EAXREVERB_DECAY_HFRATIO, 0.83)
        alEffectf(efx,  AL_EAXREVERB_DECAY_LFRATIO, 1.0)
        alEffectf(efx,  AL_EAXREVERB_REFLECTIONS_GAIN, 0.05)
        alEffectf(efx,  AL_EAXREVERB_REFLECTIONS_DELAY, 0.007)
        alEffectf(efx, AL_EAXREVERB_LATE_REVERB_GAIN, 1.25)
        alEffectf(efx, AL_EAXREVERB_LATE_REVERB_DELAY, 0.02)
        alEffectf(efx, AL_EAXREVERB_ECHO_TIME, 0.25)
        alEffectf(efx, AL_EAXREVERB_ECHO_DEPTH, 0.0)
        alEffectf(efx, AL_EAXREVERB_MODULATION_TIME, 0.24)
        alEffectf(efx, AL_EAXREVERB_MODULATION_DEPTH, 0.0)
        alEffectf(efx, AL_EAXREVERB_AIR_ABSORPTION_GAINHF, 0.994)
        alEffectf(efx, AL_EAXREVERB_HFREFERENCE, 5000.0)
        alEffectf(efx, AL_EAXREVERB_LFREFERENCE, 250.0)
        alEffectf(efx, AL_EAXREVERB_ROOM_ROLLOFF_FACTOR, 0.00)
        alEffecti(efx, AL_EAXREVERB_DECAY_HFLIMIT, 1)

        slot = ALuint()
        alGenAuxiliaryEffectSlots(1, byref(slot))
        alAuxiliaryEffectSloti(slot, AL_EFFECTSLOT_EFFECT, efx.value)
        alSource3i(wav.id.value, AL_AUXILIARY_SEND_FILTER, slot.value, 0, AL_FILTER_NULL)
        print("REVERB ENABLED")

    wav.play()
    time.sleep(2)
