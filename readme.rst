SoundServer
-----------
The sound server reads a YAML file specifying sounds to be played. Sounds can then be triggered and manipulated remotely over OSC (e.g. fading in and out tracks, 3D positioning of sounds). This allows
configuration and remote triggering/manipluation of sounds over a network. This software was designed for adding audio to interactive art installations and similar; 
it is probably not suitable for gaming or real-time musical applications.

Sound generation is via **pyfmodex**, which in turn wraps the high performance **FMODEx** library, which is used to render the sounds.  Most **FMODEx** features are supported. 

The server also supports autonomous fades, and automations for making filter changes, position movements, and pitch adjustment using random, periodic or spline based patterns. It supports
stochastic sound generation, so that random sounds can be generated server-side according to a fairly flexible random generation model.

Example OSC messages::

    # create a new transient sound mysound_0
    /sound_server/spawn mysound mysound_0
    
    # set the gain to -80dB
    /sound_server/gain mysound_0 -80    
    
    # start the sound playing
    /sound_server/start mysound_0
    
    # start a fade up to 0dB over the next 5 seconds
    /sound_server/gain mysound_0 0 5.0

Requires **numpy**, **pyfmodex** and **simpleOSC**. 

*Note:* this is currently Python 2.x only. Python 3.x may or may not work with some small changes. You must separately acquire FMODEx for your platform. Depending on your use, FMODEx
may require a commercial license.

This library relies on **pyfmodex**, which is somewhat incomplete/buggy at the moment. In particular, it does not work on 64-bit systems (you will get an FMOD_INVALID_PARAMETER error if you try and run
on a 64 bit system).  sound_server has some workarounds for missing or incomplete features in pyfmodex by calling FMODEx directly via ctypes. 

*OS X note:* On OS X, the pyfmodex library must be patched to change the **FMODEx** library name from .so to .dylib
