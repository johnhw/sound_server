import logging
import numpy as np
from derivative_estimator import SavitzkyGolay

# the global FMOD system object
system = None

# assign channels in order    
channel_ptr = 1

def new_channel():
    global channel_ptr
    logging.debug("Assigning new channel %d", channel_ptr)
    c = channel_ptr
    channel_ptr += 1
    return c
        
def from_dB(x):
    return 10.0**(x/20.0)
    
def to_dB(x):    
    return np.log10(x)*20.0 
    
    
class VelocityFilter(object):
    default_taps = 13
        
    def __init__(self, taps=None, order=3):
        self.velocity = np.array([0,0,0])
        self.order = order
        self.taps = taps or VelocityFilter.default_taps
        self.filters = [SavitzkyGolay(self.taps, order=order, deriv=1) for i in range(3)]
                
    def new_sample(self, pos):
        for i in range(3):            
            self.velocity[i] = self.filters[i].new_sample(pos[i])
            
            
    def clear(self):
        # reset the tracker to zero velocity
        self.velocity = np.array([0,0,0])
        [self.filters[i].clear() for i in range(3)]

        
