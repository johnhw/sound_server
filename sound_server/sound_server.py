import pyfmodex, time
import numpy as np
import os, sys, random, ctypes
from pyfmodex.constants import *
from collections import defaultdict
import logging, copy, atexit
from simpleOSC import *
from smooth import SmoothVal
import sound_global_state
from sound_global_state import VelocityFilter
from sound_global_state import new_channel, from_dB, to_dB
import tempfile
import multiprocessing
import Queue
from auto_sounds import Burst, AutomationGroup, Automation
import yaml

logging.basicConfig(filename=os.path.join(tempfile.gettempdir(),"sound_server.log"), level=logging.DEBUG, format='%(asctime)s:%(message)s')
logging.getLogger().addHandler(logging.StreamHandler())

# Global FMOD system object
system = pyfmodex.System()
sound_global_state.system = system

from sound_object import Sound, DSP_clock, set_channel_delay_start, set_channel_delay_pause
from sound_channel_group import ChannelGroup

def call_fmod(fn, *args):        
    result = getattr(pyfmodex.fmodobject._dll, fn)(system._ptr, *args)
    return result
    
def DSP_info():
    """Get the software mixer status from FMOD.
    Returns a dictionary of:
    sample_rate: Hz
    format: FMOD enumeration
    out_channels: number of output channels
    in_channels: number of input channels
    resampler: resampler as FMOD enumeration
    bits: bit depth"""
    sr = ctypes.c_int()   
    fmt = ctypes.c_int()
    out_ch = ctypes.c_int()
    in_ch = ctypes.c_int()
    resampler = ctypes.c_int()
    bits = ctypes.c_int()        
    call_fmod("FMOD_System_GetSoftwareFormat",  ctypes.byref(sr), ctypes.byref(fmt), ctypes.byref(out_ch), ctypes.byref(in_ch), ctypes.byref(resampler), ctypes.byref(bits))
    result = {'sample_rate':sr.value, "format":fmt.value, "out_channels":out_ch.value, "in_channels":in_ch.value, "resampler":resampler.value, "bits":bits.value}    
    return result
        

class SoundPool(object):
    """Represents a collection of sounds, which can be triggered by selecting one at random."""
    def __init__(self, pool, sound_list):
        self.name = pool['name']
        logging.debug("Sound pool %s created" % self.name)
        self.sounds = []
        for sound in pool['sounds']:
            if sound in sound_list:
                self.sounds.append(sound)
            else:
                logging.debug("Tried to add non-existent sound %s to pool %s" % (sound, self.name))
                
    def get(self):
        return random.choice(self.sounds)
        
# parameters in form (fmod_param_id, yaml_name, scaling factor)    
# scaling factor converts mB to dB
reverb_params =  {  (0, 'dry', 100.0), (1, 'room', 100.0), (2, 'room_hf', 100.0),
                    (3, 'room_rolloff', 1.0), (4,'room_decaytime', 1.0), (5, 'room_decay_hfratio', 1.0),
                    (6, 'reflections_level', 100.0), (7, 'reflections_delay', 1.0), (8, 'diffusion', 1.0),
                    (9, 'density', 1.0), (10, 'hf_reference', 1.0), (11, 'room_lf', 100.0), (12, 'lf_reference', 1.0)}


# set the speaker/surround mode enumerations
FMOD_SPEAKERMODE_SRS5_1_MATRIX = 7
FMOD_SPEAKERMODE_DOLBY5_1_MATRIX = 8
speaker_modes = {"mono":FMOD_SPEAKERMODE_MONO, "stereo":FMOD_SPEAKERMODE_STEREO,
"quad":FMOD_SPEAKERMODE_QUAD, "surround":   FMOD_SPEAKERMODE_SURROUND, "5.1":FMOD_SPEAKERMODE_5POINT1,
"7.1":FMOD_SPEAKERMODE_7POINT1, "srs5.1":FMOD_SPEAKERMODE_SRS5_1_MATRIX, "dolby5.1":FMOD_SPEAKERMODE_DOLBY5_1_MATRIX}

# id -> speaker name table
speaker_ids = dict(zip(speaker_modes.values(), speaker_modes.keys()))                    

def replace_from_yaml(defaults, replacement):            
    for key in defaults:
        defaults[key] = replacement.get(key, defaults[key])


class SoundServer(object):

    def make_eq(self, eq):
        """Make the equaliser from the YAML spec. All EQ bands are 1 octave in width"""
        for bands in eq:
            eq = system.create_dsp_by_type(FMOD_DSP_TYPE_PARAMEQ)
            eq.set_param(0, bands[0])           # centre
            eq.set_param(1, 1.0)                # octaves
            eq.set_param(2, bands[1])           # gain            
        return eq
        
    def configure_reverb(self, rev_dsp, reverb):
        """Set the reverb settings for the reverb DSP from a dictionary"""
        for id, param, scale in reverb_params:
            if param in reverb:
                rev_dsp.set_param(id, reverb[param]*scale)
                
    def make_reverb(self, reverb):
        """Creaate and configure a reverb DSP"""
        rev_dsp = system.create_dsp_by_type(FMOD_DSP_TYPE_SFXREVERB-1)        
        self.configure_reverb(rev_dsp, reverb)
        return rev_dsp
        
    
    def set_reverb(self, scene):
        """Set a new reverb, based on a reverb descriptor dictionary"""
        if not self.reverb:
            self.reverb = self.make_reverb(scene)
            system.add_dsp(self.reverb)
        else:
            self.configure_reverb(self.reverb, scene)
        logging.debug("Reverb scene %s activated" % scene['name'])
        
    def set_eq(self, eq):         
        """Set a new equaliser scene"""
        if self.eq is not None:
            for existing_eq in self.eq:                
                existing_eq.remove()
                existing_eq.release()        
        self.eq = []
        for bands in eq['bands']:
            eqdsp = system.create_dsp_by_type(FMOD_DSP_TYPE_PARAMEQ)
            eqdsp.set_param(0, bands[0])                   # centre
            eqdsp.set_param(1, bands[1])                        # octaves
            eqdsp.set_param(2, from_dB(bands[2]))           # gain         
            system.add_dsp(eqdsp)    
            self.eq.append(eqdsp)
        logging.debug("Equaliser %s active" % eq['name'])    
            
    def unique_name(self):
        self.ctr += 1
        return "name_%06d" % self.ctr

    def get_audio_devices(self):
        n_drivers =system.num_drivers
        logging.debug("%d drivers found" % n_drivers)
        drivers = {}
        for i in range(n_drivers):
            info = dict(system.get_driver_info(i))
            caps = dict(system.get_driver_caps(i))
            info["caps"] = caps
            logging.debug("Driver %d: %s" % (i,info))
            logging.debug("\t\t Capabilities: %s" % caps)
            drivers[i] = info
        return drivers
        
    def set_speaker_locations(self, spec):
        """Set the x, y positions of each speaker"""
        speaker_names = {
        "front_left":FMOD_SPEAKER_FRONT_LEFT,    
        "front_right":FMOD_SPEAKER_FRONT_RIGHT,  
        "front_center":FMOD_SPEAKER_FRONT_CENTER, 
        "low_frequency":FMOD_SPEAKER_LOW_FREQUENCY,
        "back_left":FMOD_SPEAKER_BACK_LEFT,    
        "back_right":FMOD_SPEAKER_BACK_RIGHT,   
        "side_left":FMOD_SPEAKER_SIDE_LEFT,    
        "side_right":FMOD_SPEAKER_SIDE_RIGHT}        
        for speaker in spec:
            speaker_spec = spec[speaker]
            x = speaker_spec.get('x', 0)
            y = speaker_spec.get('y', 1)
            enabled = speaker_spec.get('enabled', True)
            if enabled:
                logging.debug("Setting speaker %s to x=%.2f, y=%.2f" %(speaker, x, y) )
            else:
                logging.debug("Disabling speaker %s" % speaker)
            system.set_3d_speaker_position(speaker_names[speaker], x, y, enabled)
            
    def init_global_config(self, yaml_config):    
         # defaults
        default_config = {"ip_address":"0.0.0.0", "port":8001, "update_rate":100.0, "base_path":'.', "channels":96, "dsp_jitter":0.01, "audio_device":None,
        'n_buffers':8, 'buffer_size':1024, "speaker_mode":"stereo", "speaker_location":{}, "spatial_scale":1.0, "doppler_scale":0.0,
        "velocity_filter":13}                       
        replace_from_yaml(default_config, yaml_config)    
        logging.debug("Global configuration: %s" % default_config)
        config = default_config        
        
        self.speaker_mode = str(config["speaker_mode"])
        system.speaker_mode = speaker_modes[self.speaker_mode]        
        
        # velocity filtering
        VelocityFilter.default_taps = config['velocity_filter']
        # choose the appropriate audio device
        self.device = 0
        if config["audio_device"]:
            logging.debug("Looking for audio device: %s" % config['audio_device'])
            found = False
            for device in self.audio_devices:                
                if config['audio_device'] in self.audio_devices[device]['name']:
                    self.device = device
                    logging.debug("Matched audio device: %s" % self.audio_devices[device]['name'])
                    found = True
                    break
            if not found:
                logging.debug("Could not find a matching audio device %s; using default" % config['audio_device'])                    
        else:
            logging.debug("Using default audio device")
        system.driver = self.device
            
        # set spatial/doppler scaling
        logging.debug("Setting world 3D scaling to %.3f; doppler: %.2f" % (config['spatial_scale'], config['doppler_scale']))
        threed = system.threed_settings
        threed.distance_factor = config['spatial_scale']
        system.threed_settings.doppler_scale = config['doppler_scale']
        # set speakers 
        self.set_speaker_locations(config["speaker_location"])
        # set the buffering
        buffer = system.DSP_buffer_size
        buffer.size = config['buffer_size']
        buffer.count = config['n_buffers']        
            
        # set number of channels
        system.software_channels = config['channels']
                
        # configure network 
        self.ip_address = config['ip_address']
        self.port = config['port']
        logging.debug("Networking configured on %s:%d" % (self.ip_address, self.port))
        
        self.update_rate = config['update_rate']
        logging.debug("Update rate: %.2f updates/sec" % self.update_rate)
                
        self.path = config['base_path']
        logging.debug("Loading sounds from %s/" % self.path)
        self.jitter = config['dsp_jitter']
        
        
    
    def __init__(self, yaml):
        self.audio_devices = self.get_audio_devices()                
        
        self.init_global_config(yaml.get("config", {}))
        
        if self.speaker_mode=='stereo':
            system.init(flags=FMOD_INIT_NORMAL|FMOD_INIT_SOFTWARE_HRTF)
        else:
            system.init(flags=FMOD_INIT_NORMAL)
             
        logging.debug("FMOD initialised")
        
        # verify that FMOD has set the parameters like we requested
        self.dsp_info = DSP_info()
        self.driver = self.audio_devices[system.driver]
        
        logging.debug("FMOD mixer settings: %s" % self.dsp_info)
        logging.debug("FMOD speaker settings: %s" % speaker_ids[system.speaker_mode])
        if system.speaker_mode != speaker_modes[self.speaker_mode]:
            logging.debug("Speaker mode %s NOT set" % (self.speaker_mode))
        
        logging.debug("FMOD using driver: %s" % self.driver)
        logging.debug("FMOD software channels available: %d" % system.software_channels)
        
        buffer = system.DSP_buffer_size
        logging.debug("FMOD buffer size set to %d of %d samples" % (buffer.count, buffer.size))
                    
        
        # set up listener
        listener_cfg = {"position":[0,0,0], "up":[0,1,0], "forward":[0,0,1]}
        replace_from_yaml(listener_cfg, yaml.get('listener', {}))        
            
        listener = system.listener()
        listener.pos = listener_cfg['position']
        listener.vel = [0,0,0]
        listener.up = listener_cfg['up']
        listener.fwd = listener_cfg['forward']
        self.listener = listener
    
        logging.debug("Listener set")
            
        self.ctr = 0
        self.running = False    
        
        # add the channel groups and sounds
        self.sounds = {}
        self.channel_groups = {}
        self.bursts = {}
        self.automations = {}
        self.pools = {}      
        self.eqs = {}
        self.reverbs = {}        
        self.sync_times = {}
        
        def objects_from_yaml(dict, cl, yaml_block):            
            for group in yaml.get(yaml_block,[]):                
                try:
                    c = cl(group)
                    dict[c.name] = c
                except:
                    logging.exception("Could not create YAML object %s (%s)", yaml_block, group)
            logging.debug("%s created" % yaml_block)
                
        objects_from_yaml(self.channel_groups, ChannelGroup, "channel_groups")
        # now form subgroup attachements        
        [ch_group.setup_subgroups(self.channel_groups) for ch_group in self.channel_groups.values()]
        
        top_level = []
        # add top level groups to the master
        for ch_group in self.channel_groups.values():
            if ch_group.parent==None:                
                top_level.append(ch_group)
                system.master_channel_group.add_group(ch_group.group)
        master_group = ChannelGroup({'name':'master'})
        master_group.subgroups = top_level
        master_group.group = system.master_channel_group
        self.channel_groups['master'] = master_group
                        
        self.sample_rate = self.dsp_info['sample_rate']
        time_jitter = self.jitter*self.sample_rate
        objects_from_yaml(self.sounds, lambda x: Sound(x, self.channel_groups, self.path, dsp_jitter=time_jitter), "sounds")
        
        self.reverb = None
        self.eq = None
        if 'reverbs' in yaml:
            for reverb in yaml['reverbs']:
                self.reverbs[reverb['name']] = reverb
            # add the default reverb, if there is one
        if 'default' in self.reverbs:
            self.set_reverb(self.reverbs['default'])
            logging.debug("Reverb set and active")
                    
        if 'eqs' in yaml:
            for eq in yaml['eqs']:
                self.eqs[eq['name']] = eq
            # add the default reverb, if there is one
        if 'default' in self.eqs:
            self.set_eq(self.eqs['default'])
            logging.debug("EQ set and active")
        
        
        objects_from_yaml(self.bursts, Burst, "bursts")              
        objects_from_yaml(self.automations, Automation, "automations")
        objects_from_yaml(self.pools, lambda x:SoundPool(x, self.sounds), "pools")
                
        self.sounds_and_channels = dict(self.sounds.items() + self.channel_groups.items())
        self.automation_attachements = {}
        self.enable_automations()
        logging.debug("Sounds created")
                    
    def enable_automations(self):
        """Enable all automations specified in the yaml file."""
        for sound in self.sounds_and_channels:
            for auto in self.sounds_and_channels[sound].automation_blocks:
                logging.debug("Attaching automation %s to sound %s" % (auto, sound))
                # give each automation a known unique name
                self.attach_automation(sound, auto, "%s_%s" % (auto, self.unique_name()))                
    
    def update(self, dt):        
        """Update all sounds, channel groups, stochastic burst handlers, then delete any finished sounds"""
        # handle spawing events from the bursts
        for burst in self.bursts.keys():
            b = self.bursts[burst]            
            trigger = b.update(dt)            
            if trigger:                
                pool, gain, position = trigger  
                name = self.unique_name()
                self.spawn_pool(pool, name)
                snd = self.sounds[name]
                snd.gain.set_with_time(gain, 0.0)
                snd.position.set_with_time(np.array(position), 0.0)                
                self._start_sound(snd,[])
                 
        kill_list = []                  
        # and then each of layers (e.g. to make sure fades take effect)
        for sound in self.sounds.keys():
            snd = self.sounds[sound]
            if snd is None or snd.finished:
                kill_list.append(sound)
            else:
                snd.update(dt)
                
        # each of the channel groups (must do this after sounds for override to work)
        
        for ch_group in self.channel_groups.keys():
            self.channel_groups[ch_group].update(dt)      
             
        for sound in kill_list:
            if self.sounds[sound] is not None and self.sounds[sound].transient:
                logging.debug("Removing finished sound %s" % sound)            
                del self.sounds[sound]
        # update FMOD        
        system.update()
            
   
        
    def spawn_sound(self, sound, spawn_name):
        """Spawn a new transitory sound"""
        if self.sounds[sound].transient:
            new_sound = self.sounds[sound].spawn()
            self.sounds[spawn_name] = new_sound
            self.sounds_and_channels[spawn_name] = new_sound
        else:
            logging.debug("Tried to spawn a non transient sound %s" % sound)        
        
    def spawn_pool(self, pool, spawn_name):
        sound = self.pools[pool].get()
        self.spawn_sound(sound, spawn_name)                                
       
        
    def _start_sound(self, sound, sync):
            channel = sound.get_channel()
            if channel:
                # allow sync to previous marks
                if len(sync)>0:
                    sync_point, sync_time = sync                
                    if sync_point in self.sync_times:
                        dsp_clock = self.sync_times[sync_point]
                        set_channel_delay_start(channel, int(dsp_clock + sync_time * self.sample_rate))
                    else:
                        logging.debug("Tried to sync to non-existent sync point %s" % sync_point)
                channel.paused = False
    
    def _stop_sound(self, sound, sync):
            channel = sound.get_channel()
            if channel:
                # allow sync to previous marks
                if len(sync)>0:
                    sync_point, sync_time = sync                
                    if sync_point in self.sync_times:
                        dsp_clock = self.sync_times[sync_point]
                        set_channel_delay_pause(channel, int(dsp_clock + sync_time * self.sample_rate))
                    else:
                        logging.debug("Tried to sync to non-existent sync point %s" % sync_point)
                else:
                    channel.paused = True
                        
    def set_burst_enable(self, burst, state):
        if burst in self.bursts:
            self.bursts[burst].enabled = state
        else:
            logging.debug("Tried to enable/disable non-existent burst %s" % (burst))
    
    def set_reverb_scene(self, reverb):
        if reverb in self.reverbs:
            self.set_reverb(self.reverbs[reverb])
        else:
            logging.debug("Tried to set non-existent EQ scence %s" % (reverb))
            
    def set_eq_scene(self, eq):
        if eq in self.eqs:
            self.set_eq(self.eqs[eq])
        else:
            logging.debug("Tried to set non-existent EQ scence %s" % (eq))

    def force_update(self, sound):
        if sound in self.sounds:
            self.sounds[sound].update(1e-6)
            system.update()
        else:
            logging.debug("Tried to force update non-existent sound %s" % sound)
            
    def seek_sound(self, sound, time):
        channel = sound.get_channel()
        if channel:
            channel.set_position(int(time * self.sample_rate), FMOD_TIMEUNIT_PCM)
            
    def attach_automation(self, s, auto, name):
        if s in self.sounds_and_channels:
           self.sounds_and_channels[s].automations.add(name, self.automations[auto])
           self.automation_attachements[name] = s                          
        else:
            logging.debug("Tried to add automation to non-existent sound/channel %s" % s)
    
    def detach_automation(self, name):
        if name in self.automation_attachements:
            s = self.automation_attachements[name]
            self.sounds_and_channels[s].automations.remove(name)
            del self.automation_attachements[name]
        else:
            logging.debug("Tried to remove non-existent automation %s" % name)
            
    def start_group(self, ch_group, args):
        """Start all sounds on a channel group, and its subgroups"""        
        for sound in ch_group.sounds:                        
            self._start_sound(sound, args)       
        # and apply recursively to subgroups
        for group in ch_group.sub_group_channels:
            self.start_group(group, args)
            
    def stop_group(self, ch_group, args):
        """Stop all sounds on a channel group, and its subgroups"""
        for sound in ch_group.sounds:                        
            self._stop_sound(sound, args)   
        # and apply recursively to subgroups
        for group in ch_group.sub_group_channels:
            self.stop_group(group, args)
            
    def set_group_gain(self, group, gain, time):
        for sound in self.channel_groups[group].sounds:            
            sound.gain.set_with_time(gain, time)
        # propagate to subgroups
        for subgroup in self.channel_groups[group].sub_group_channels:
            self.set_group_gain(subgroup, gain, time)

    def queue_handle_osc(self, addr, tags, data, source):
        
        try:
            self.osc_queue.put((addr, tags, data, source))
        except Queue.Full:
            pass
        except:
            logging.exception("Queue put failure")
        
    def handle_osc(self, addr, tags, data, source):
        """Handle incoming OSC messages and dispatch to the appropriate handlers"""
        logging.debug("OSC message: %s %s %s %s" % (addr, tags, data, source))
        addr = '/' + '/'.join(addr.split('/')[1:])
        try:
        
            if addr=='/sound_server/spawn':
                if data[0] in self.sounds:
                    self.spawn_sound(data[0], data[1])         
                elif data[0] in self.pools:
                    self.spawn_pool(data[0], data[1])                             
                else:
                    logging.debug("Tried to spawn non-existent sound/pool: %s" % data[0])
            
            
            def set_attr(test_addr, attr):                
                if addr==test_addr:
                    s, db = data[0], data[1]
                    if len(data)>2:
                        time = data[2]
                    else:
                        time = 0.0
                    if s in self.sounds_and_channels:
                        getattr(self.sounds_and_channels[s], attr).set_with_time(db, time) 
                    else:
                        logging.debug("%s tried to set %s of non-existent %s" % (addr, attr, s))
                        
                     
            set_attr('/sound_server/gain', 'gain')
            set_attr('/sound_server/frequency', 'frequency')
            set_attr('/sound_server/filter', 'filter_val')            
            
            if addr=='/sound_server/position':
                if len(data)>4:
                    time = data[4]
                else:
                    time = 0.0
                s, pos = data[0], np.array((data[1], data[2], data[3]))                
                if s in self.sounds:
                    self.sounds[s].position.set_with_time(pos, time) 
                    if time==0.0:
                        self.sounds[s].clear_velocity()
                elif s in self.channel_groups:
                    # disable position override on a string parameter
                    if isinstance(data[1], basestring):
                        self.channel_groups[s].position_set = False       
                    else:
                        self.channel_groups[s].position.set_with_time(pos, time)   
                        if time==0.0:
                            self.channel_groups[s].clear_velocity()
                        self.channel_groups[s].position_set = True  

            if addr=='/sound_server/group_gain':
                s = data[0]
                if len(data)>2:
                    time = data[2]
                else:
                    time = 0.0                
                if s in self.channel_groups:
                    self.set_group_gain(s, data[1], time)
                    
                        
            if addr=='/sound_server/start':  
                s = data[0]
                if s in self.sounds:                    
                    self._start_sound(self.sounds[s], data[1:])
                elif s in self.channel_groups:
                    ch_group = self.channel_groups[s]
                    self.start_group(ch_group, data[1:])                              
                else:
                    logging.debug("Tried to start a non-existent sound %s" % s)                                                      
                    
            if addr=='/sound_server/stop':
                s = data[0]
                if s in self.sounds:                    
                    self._stop_sound(self.sounds[s], data[1:])
                elif s in self.channel_groups:
                    ch_group = self.channel_groups[s]
                    self.stop_group(ch_group, data[1:])                                                  
                else:
                    logging.debug("Tried to stop a non-existent sound %s" % s)                                    
                    
                
            if addr=='/sound_server/mute' or addr=='/sound_server/unmute':
                s = data[0]
                muted = addr=='/sound_server/mute'
                if s in self.channel_groups:
                    self.channel_groups[s].muted = muted
                elif s in self.sounds:
                    channel = self.sounds[s].get_channel()
                    if channel is not None:
                        channel.mute = muted
                    else:
                        logging.debug("Tried to mute non-playing sound %s" % s)
                else:
                    logging.debug("Tried to mute non-existent sound/channel %s" % s)
                    
                                
            if addr=='/sound_server/burst/enable':
                self.set_burst_enable(data[0], True)
            if addr=='/sound_server/burst/disable':
                self.set_burst_enable(data[0], False)
                
            if addr=='/sound_server/automation/add':
                s, auto, name = data[0], data[1], data[2]
                self.attach_automation(s, auto, name)
                
            if addr=='/sound_server/automation/remove':
                name = data[0]
                self.detach_automation(name)
      
            if addr=='/sound_server/listener/position':                
                self.listener.position = data[0:3]
            if addr=='/sound_server/listener/up':
                self.listener.up = data[0:3]
            if addr=='/sound_server/listener/fwd':
                self.listener.fwd = data[0:3]               
            if addr=='/sound_server/shutdown':
                self.running = False                
            if addr=='/sound_server/reverb':
                self.set_reverb_scene(data[0])
            if addr=='/sound_server/eq':
                self.set_eq_scene(data[0])
            if addr=='/sound_server/sync':
                self.sync_times[data[0]] = DSP_clock()
            if addr=='/sound_server/seek':
                s = data[0]
                if s in self.sounds:                    
                    self.seek_sound(self.sounds[s], data[1])
                elif s in self.channel_groups:
                    ch_group = self.channel_groups[s]
                    for sound in ch_group.sounds:                        
                        self.seek_sound(sound, data[1])    
                else:
                    logging.debug("Tried to seek non-existent sound/channel %s" % s)
                    
            if addr=='/sound_server/loop':
                s = data[0]
                if s in self.sounds:                                        
                    if len(data)==2:
                        self.sounds[s].set_loop(data[1], None)                    
                    else:
                        self.sounds[s].set_loop(data[1], (data[2], data[3]))                    
                else:
                    logging.debug("Tried to set looping non-existent sound %s" % s)

            # force OSC messages to trigger an update for reduced latency
            self.update(1e-8)
        except:
            logging.exception("OSC handling error")
            
    def setup_OSC(self):
        initOSCServer(self.ip_address, self.port)
        msgs = ["spawn", "filter", "gain",  "start", "stop", "position",
        "filter",  "mute", "unmute", "eq",  "group_gain",     
         "automation/add",  "automation/remove", "shutdown", 'reverb', 'burst/enable', 'burst/disable', 
         'listener/position', 'listener/fwd', 'listener/up', 'sync', 'seek', 'frequency', 'loop'
        ]        
        for msg in msgs:
            setOSCHandler('/sound_server/'+msg, self.handle_osc)
        self.addresses = msgs
        startOSCServer()
        logging.debug("OSC server launched")
        
    def close(self):
        logging.debug("OSC server closing")
        closeOSC()
        os._exit(1)

    def handle_queue(self):
        more_osc = True        
        while more_osc:
            try:
                addr, tags, data, source = self.osc_queue.get_nowait()
                self.handle_osc(addr, tags, data, source)
            except Queue.Empty:
                more_osc = False
                pass
            except:
                logging.exception("Handle queue empty")
                
    def get_messages(self):
        """Return available addresses for OSC commands"""
        return self.addresses

        
    def run(self):
        """Enter the main loop. Runs until a /sound_server/shutdown message is received."""
        self.running = True
        t = time.time()
        start_t = time.time()
        # automate fade out on exit            
        master = system.master_channel_group
        master.volume  = 0.0
        self.osc_queue = multiprocessing.Queue()
        self.setup_OSC()
        fade_in_time = 0.5
        logging.debug("Listening loop entered; beginning fade in")
        try:
            while self.running:            
                time.sleep(1.0/self.update_rate)            
                t_n = time.time()            
                # apply fade in if needed
                if t_n - start_t<fade_in_time:
                    # fade in
                    fade = (1-((t_n - start_t) / fade_in_time)) * -80                    
                    master.volume = from_dB(fade)    
                try:
                    self.handle_queue()
                except:
                    logging.exception("Queue read failed")            
                try:                                    
                    self.update(t_n - t)
                except (KeyboardInterrupt):
                    logging.exception("Keyboard forced exit")
                    self.running = False
                except:
                    logging.exception("Exception in update loop; continuing")                
                t = t_n
        except:
            logging.exception("Exception in sound_server main loop; fading out")
        
        # close OSC and fade out
        self.close()        
        master = system.master_channel_group
        
        logging.debug("Master fade out initiated")
        for i in range(0, 140):
            time.sleep(0.01)
            master.volume = from_dB(to_dB(master.volume) - 1)
            
        logging.debug("Master fade out complete")    
        
            

# recursively merge nested dictionaries. code from http://stackoverflow.com/questions/7204805/dictionaries-of-dictionaries-merge                
def mergedicts(dict1, dict2):
    for k in set(dict1.keys()).union(dict2.keys()):
        if k in dict1 and k in dict2:
            if isinstance(dict1[k], dict) and isinstance(dict2[k], dict):
                yield (k, dict(mergedicts(dict1[k], dict2[k])))
            else:
                yield (k, dict2[k])                
        elif k in dict1:
            yield (k, dict1[k])
        else:
            yield (k, dict2[k])

            
def launch_with_configs(configs):
        """Launch with a set of configurations, with later configurations overriding previous ones"""
        config = {}        
        yaml_configs = []
        for yamls in configs:                
            logging.debug("Importing/merging YAML config %s" % yamls)
            with open(yamls) as f:                
                yaml_configs.append(yaml.load(f))                
        config = dict(reduce(mergedicts, yaml_configs))        
        server = SoundServer(config)
        server.run()


        
def launch(config):
   """Launch the sound server with the given configuration file"""
   
   launch_with_configs([config])

                        
if __name__=="__main__":       
    launch_with_configs(sys.argv[1:])
        
        
        
    
    
    
    
