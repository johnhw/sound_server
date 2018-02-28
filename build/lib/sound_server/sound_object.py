import pyfmodex, time, yaml
import numpy as np
import os
import random
import ctypes
from pyfmodex.constants import *
import logging, copy
from smooth import SmoothVal
from sound_global_state import new_channel, from_dB, VelocityFilter
import sound_global_state
from auto_sounds import AutomationGroup

system = None

# get DSP clock (pyfmodex is incorrect)        
def DSP_clock():
    hi = ctypes.c_uint()   
    lo = ctypes.c_uint()
    result = pyfmodex.fmodobject._dll.FMOD_System_GetDSPClock(system._ptr, ctypes.byref(hi), ctypes.byref(lo))
    return (int(hi.value)<<32) | int(lo.value)
    
def set_channel_delay_start(channel, dsp_time):
    pyfmodex.fmodobject._dll.FMOD_Channel_SetDelay(channel._ptr, FMOD_DELAYTYPE_DSPCLOCK_START, (dsp_time>>32), (dsp_time&0xffffffff))

def set_channel_delay_pause(channel, dsp_time):
    pyfmodex.fmodobject._dll.FMOD_Channel_SetDelay(channel._ptr, FMOD_DELAYTYPE_DSPCLOCK_PAUSE, (dsp_time>>32), (dsp_time&0xffffffff))
    
class Sound(object):
    """Representation of a sound object. Each sound_descriptor is a single Sound object. 
    Transient sounds have a prototype Sound object which is configured on 
    start up. New sounds can be generated by calling spawn(), which copies
    the object and assigns a channel from the channel group for that transient sound
    
    Every transient sound must have a channel group.
    update() must be called regularly to update the sound's position, gain and filtering. """
    def __init__(self, sound_descriptor, channel_groups, base_path, dsp_jitter=0):
        global system
        system = sound_global_state.system # make sure FMOD object is initialised
        self.name = sound_descriptor['name']
        logging.debug("Creating sound %s, descriptor:\n%s" % (self.name, yaml.dump(sound_descriptor, indent=4)))        
        self.dsp_jitter = dsp_jitter 
        # create the sound
        
        self.filename = sound_descriptor['file']        
        self.sound = system.create_sound(os.path.join(base_path, self.filename))
        self.base_frequency = self.sound.default_frequency
        logging.debug("Base frequency is %d Hz" % (self.base_frequency))
        self.automation_blocks = sound_descriptor.get('automation', [])
            
        
        logging.debug("Sound file %s loaded succesfully" % self.filename)
        self.sound.min_distance = sound_descriptor.get('min_distance', 10.0)
        self.position = SmoothVal(np.array(sound_descriptor.get('position', [0,0,0])), 0.01)
        self.doppler = sound_descriptor.get('doppler', 0.0)
        
        self.spread = sound_descriptor.get("stereo_spread", 0.0) 
        self.sound.position = self.position.state
        self.velocity = VelocityFilter()
        self.clear_velocity()        
        self.loop_points = sound_descriptor.get('loop_points', None)
        self.looping = sound_descriptor.get('loop', False)
        self.loop_count = sound_descriptor.get('loop_count', -1)
        self.filter = sound_descriptor.get('filter', None)
        self.gain = SmoothVal(sound_descriptor.get('gain', 0.0),0.05, linear=True)        
        self.frequency = SmoothVal(sound_descriptor.get('frequency', 1.0), 0.05)        
        self.filter_val = SmoothVal(0,0)
        
        self.finished = False
        self.filter = False            
        # add low pass filtering if needed
        if 'filter' in sound_descriptor:
            self.filter = True
            self.filter_val = SmoothVal(sound_descriptor['filter'], 0.01)                                    
                           
        self.channel_group = None
        # set the channel group, if there is one
        if 'channel_group' in sound_descriptor:
            ch_group = channel_groups.get(sound_descriptor['channel_group'], None)
            if ch_group is not None:
                self.channel_group = ch_group
                self.channel_group.register_sound(self)
            else:
                logging.debug("Tried to assign sound %s to non-existent channel group %s" % (self.name, ch_group))
                
        self.channel_id = None        
        self.transient = sound_descriptor.get('transient', False)
        if not self.transient:
            # spawn immediately if layer
            self.assign_channel(new_channel())
            
        self.automations = AutomationGroup()
        
    def set_doppler(self, doppler):
        """Set the doppler factor"""
        self.doppler = doppler
        channel = self.get_channel()
        if channel:
            self.channel.doppler_level = self.doppler
            
    def clear_velocity(self):
        self.velocity.clear()
        
    def set_loop(self, loop, loop_points):
        """Set the looping state for this sound."""
        channel = self.get_channel()
        self.looping = loop
        self.loop_points = loop_points
        if self.looping:
            channel.mode = FMOD_LOOP_NORMAL            
            self.sound.loop_count = self.loop_count
        else:
            channel.mode = FMOD_LOOP_OFF           
        if self.loop_points is not None:        
            channel.loop_points = (int(self.loop_points[0]*self.base_frequency), FMOD_TIMEUNIT_PCM), (int(self.loop_points[1]*self.base_frequency), FMOD_TIMEUNIT_PCM)
            
                    
    def assign_channel(self, channel_id):
        """Assign a channel to this sound, and configure the channel properties.
        Channels start in the paused state (i.e. are silent). Call start() to start playback
        """                
        # create the channel for this layer        
        
        system.play_sound(self.sound, channelid=channel_id, paused=True)
        channel = system.get_channel(channel_id)
            
        logging.debug("Assigning channel to sound %s" % self.name)
        channel.volume = from_dB(self.gain.state)        
        channel.paused = True        
        channel.doppler_level = self.doppler
        channel.threed_spread = self.spread
        
        # adjust delay to avoid machine gunning
        dsp_time = DSP_clock()        
        dsp_time = dsp_time+random.randint(0, self.dsp_jitter)        
        # work around pyfmodex bug
        pyfmodex.fmodobject._dll.FMOD_Channel_SetDelay(channel._ptr, FMOD_DELAYTYPE_DSPCLOCK_START, (dsp_time>>32), (dsp_time&0xffffffff))
        
        channel.channel_group = self.channel_group.group
        if self.filter:
            lp_filter = system.create_dsp_by_type(FMOD_DSP_TYPE_LOWPASS)            
            lp_filter.set_param(0, self.filter_val.state)
            channel.add_dsp(lp_filter)
            self.lp_filter = lp_filter
        self.channel_id = channel_id     
        self.set_loop(self.looping, self.loop_points)        
        system.update()
                
    def test_channel(self, channel):
        pl = ctypes.c_bool()        
        result = pyfmodex.fmodobject._dll.FMOD_Channel_IsPlaying(channel._ptr, ctypes.byref(pl))
        return result==FMOD_OK        
        
    def get_channel(self):
        if self.channel_id is None:
            return None
        channel = system.get_channel(self.channel_id)
        if not self.test_channel(channel):            
            self.channel_id = None
            self.finished = True
            return None        
        return channel
            
                   
        
    def spawn(self):
        """Find a free channel in this sound's channel group, and then play
        the sound on that channel. Returns a reference to a new Sound object
        which has the active channel. 
        If no free channels are found, a random channel is overwritten.
        """
        # find a channel in the assigned group, and play on that
        if not self.channel_group:
            logging.debug("Sound %s tried to spawn without a channel group" % self.name)
            return
        logging.debug("Sound %s spawning" % self.name)
        chans = self.channel_group.sub_channels
        potentials = []
        for chan in chans:                        
            channel = system.get_channel(chan)            
            if self.test_channel(channel):
                if not channel.is_playing:
                    potentials.append(chan)                
            else:
                potentials.append(chan) 
            
        # no free channels, choose a random one
        if len(potentials)==0:
            chan = random.choice(self.channel_group.sub_channels)                        
            channel = system.get_channel(chan)
            channel.stop()
            system.update()
            potentials.append(chan)
            logging.debug("No free channel was available; randomly stopping one")
        else:
            logging.debug("Free channel found.")
        channel = random.choice(potentials)
        # now copy this sound and allocate it a channel
        new_sound = copy.deepcopy(self)
        new_sound.sound = self.sound # make sure reference is correct
        new_sound.assign_channel(channel)
        return new_sound        
                
    def mute(self):
        if self.channel_id:
            self.get_channel().mute = True
        
    def unmute(self):
        if self.channel_id:            
            self.get_channel().mute = False
        
    def set_volume(self, gain, time=0.01):
        self.gain.set_with_time(gain, time)
        
    
    def set_filter(self, filter, time=0.01):
        self.filter_val.set_with_time(filter, time)        
        
    def set_position(self, position, time=0.01):
        self.position.set_with_time(position, time)
            
    def start(self):
        if self.channel_id:
            self.update()
            self.get_channel().paused = False            
            logging.debug("Sound %s started" % self.name)
        
    def stop(self):
        if self.channel:
            self.get_channel().paused = True
            logging.debug("Sound %s stopped" % self.name)
        
    def update(self, dt):
        # update the position, gain and filtering of this channel
        # must have an active channel to update the state
        channel = self.get_channel()
        self.automations.update(dt)
        if not channel:
            return                  
        self.frequency.update(dt)
        self.position.update(dt)         
        channel.frequency = self.frequency.state * self.base_frequency
        
        position = self.position.state + self.automations.get('position')
        
        channel.position = position       
        self.velocity.new_sample(position)        
        channel.velocity = list(self.velocity.velocity)
        self.gain.update(dt)
        channel.volume = from_dB(self.gain.state + self.automations.get('gain'))
        if self.filter:
            self.filter_val.update(dt)           
            cutoff = self.filter_val.state + self.automations.get('filter')        
            if cutoff>20000:
                self.lp_filter.bypass = True           
            else:
                self.lp_filter.bypass = False
                self.lp_filter.set_param(0, cutoff)
                    