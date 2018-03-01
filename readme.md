# SoundServer
The sound server reads a YAML file specifying sounds to be played. Sounds can then be triggered and manipulated remotely over OSC (e.g. fading in and out tracks). This allows
remote configuration and manipluation of sounds in realtime over a network. Pyfmodex and FModEx are used to render the sounds.  Most FModEx features are supported. 

# OpenAL setup
OpenAL SOFT must be installed, and the relevant DLL/shared library file (e.g. `openal64.dll` or `openal32.dll`) must be present.
The include files from the source repository (`include/AL`) must be downloaded and copied into the `openal/` folder (note: these are not distributed
with this package as they are GPL licensed; they are parsed to extract the call signatures and constant definitions)

  openal/
      al.h
      alc.h
      alext.h
      efx.h

Configuration for OpenAL is read from `openal/openal.cfg`



## Example
Example YAML configuration:

    ---
    config:
        # number of mixer channels available
        channels: 96
        
        # base path to prepend to all sound filenames
        base_path: .

        # update rate of the server, in Hz
        update_rate: 100.0
            
        # port and IP to listen on for the OSC server    
        ip_address: 0.0.0.0
        port: 8000

    channel_groups:

        -   name: creatures
            transient_channels: 8
            gain: -14

    sounds:
        - name: creature_1
          transient: True
          min_distance: 1000
          file: creature_1.wav
          channel_group: creatures
        
        - name: creature_2
          transient: True
          min_distance: 1000
          file: creature_2.wav
          channel_group: creatures
        
        - name: creature_3
          transient: True
          min_distance: 1000
          file: creature_3.wav
          channel_group: creatures
          
        - name: creature_4
          transient: True
          min_distance: 1000
          file: creature_4.wav
          channel_group: creatures

    pools:               
        - name: creatures
          sounds: 
            - creature_1 
            - creature_2 
            - creature_3        
            - creature_4            
                   

    
Example OSC messages for this config:

    # spawn a sound (but don't start it yet)
    /sound_server/spawn, creatures, c1
    
    # start the sound
    /sound_server/start, c1
    
    # spawn another sound
    /sound_server/spawn, creatures, c2
    
    # gain to -80dB before starting
    /sound_server/gain, creatures, -80
    
    /sound_server/start, c2
    # gain fades up to 0dB in 0.5 seconds
    /sound_server/gain, creatures, 0, 0.5 

