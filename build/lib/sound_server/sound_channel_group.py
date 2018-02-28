import pyfmodex, time, yaml
from sound_global_state import new_channel, from_dB, system, VelocityFilter
import logging
from smooth import SmoothVal
from pyfmodex.constants import *
import ctypes
from pyfmodex.structures import VECTOR
from auto_sounds import AutomationGroup, Automation
import numpy as np

def add_dsp_channel_group(ch_group, dsp):
    # work around PyFMODEx bug
    c_ptr = ctypes.c_int(0)            
    result = getattr(pyfmodex.fmodobject._dll, "FMOD_ChannelGroup_AddDSP")(ch_group._ptr, dsp._ptr, ctypes.byref(c_ptr))    
    assert(result==FMOD_OK)
    
def set_pitch_channel_group(ch_group, p):
    result = getattr(pyfmodex.fmodobject._dll, "FMOD_ChannelGroup_SetPitch")(ch_group._ptr, ctypes.c_float(p))    
    assert(result==FMOD_OK)
    
class ChannelGroup(object):
    def __init__(self, ch_group):
        """Create a new channel group from a dictionary specification.
        The channel group can have transitory (blank) channels on which
        transient sounds can be played, or can have channels added later when 
        layers are loaded."""
        self.name = ch_group['name']
        self.position_set = False
        self.automation_blocks = ch_group.get('automation', [])
        self.velocity = VelocityFilter()
        self.clear_velocity()        
        self.subgroups = ch_group.get('subgroups', [])
        self.position = SmoothVal(np.array([0,0,0]), 0.01)
        logging.debug("Creating channel descriptor %s:\n%s" % (self.name, yaml.dump(ch_group)))
        self.muted = ch_group.get('mute', False)
        self.gain = SmoothVal(ch_group.get('gain', 0.0), 0.01, linear=True)
        self.frequency = SmoothVal(ch_group.get('frequency', 1.0), 0.05) 
        self.parent = None
        self.filter_val = SmoothVal(ch_group.get('filter', 48000), 0.01)
        lp_filter = system.create_dsp_by_type(FMOD_DSP_TYPE_LOWPASS)            
        lp_filter.set_param(0, self.filter_val.state)
        self.sub_group_channels = []
        self.transient_channels = ch_group.get('transient_channels', 0)
        self.sub_channels = []
        self.automations = AutomationGroup()
        self.sounds = []
        self.group = system.create_channel_group(self.name)                
        add_dsp_channel_group(self.group, lp_filter)        
        self.lp_filter = lp_filter
        
        # attach to the master
        system.master_channel_group.add_group(self.group)
        
        for i in range(self.transient_channels):       
            chan = new_channel()
            self.sub_channels.append(chan)
          
        self.update(0.0)
        
    def clear_velocity(self):
        self.velocity.clear()
        
        
    def setup_subgroups(self, channel_groups):
        """Attach the subgroups; must be called after all channel groups initialised"""
        for group in self.subgroups:
            if group in channel_groups:
                ch_group = channel_groups[group].group
                self.sub_group_channels.append(channel_groups[group])
                self.group.add_group(ch_group)
                channel_groups[group].parent = self                
            else:
                logging.debug("Channel group %s has non-existent subgroup %s" % (self.name, group))
        
    def register_sound(self, sound):
        """Register a sound as belonging to this channel; used for whole group starts / stops"""
        self.sounds.append(sound)
        
    
    def update(self, dt):
        """Update the gain and mute state of this channel group"""
        self.automations.update(dt)
        self.gain.update(dt)                
        self.filter_val.update(dt)
        self.position.update(dt)
        self.frequency.update(dt)
        # work around bug in pyfmodex
        self.group._call_fmod("FMOD_ChannelGroup_SetMute", self.muted)                
        self.group.volume = from_dB(self.gain.state + self.automations.get('gain'))
        position = np.array(self.position.state) + np.array(self.automations.get('position'))
        self.velocity.new_sample(position)
        if self.position_set:            
            v = VECTOR.from_list(list(position))
            v_vel = VECTOR.from_list(list(self.velocity.velocity))                        
            self.group.override_3d_attributes(ctypes.byref(v), ctypes.byref(v_vel))
        else:
            self.group.override_3d_attributes(0, 0)
                    
        # adjust filter cutoff
        cutoff = self.filter_val.state + self.automations.get('filter')                
        set_pitch_channel_group(self.group, self.frequency.state)
        if cutoff>20000:
            self.lp_filter.bypass = True           
        else:
            self.lp_filter.bypass = False
            self.lp_filter.set_param(0, cutoff)