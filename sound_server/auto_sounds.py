import random, logging
import copy
from smooth import SmoothVal
from collections import defaultdict
import numpy as np
from spline import CardinalSpline

    
class Gilbert(object):
    """implementS a Gilbert Markov chain, which can switch between two states. Simulates
    bursty behaviour."""    
    def __init__(self, p1, p2):
        self.p1 = p1
        self.p2 = p2
        self.state = 0        
    
    def update(self, dt):
        # account for sampling rate              
        p1 = 1-((1-self.p1)**(dt))
        p2 = 1-((1-self.p2)**(dt))
        
        if self.state==0:            
            if random.random()<p1:
                self.state = 1
        if self.state==1:            
            if random.random()<p2:
                self.state = 0


class SineAutomation(object):
    """An automation proxy which oscillates at a given frequency"""
    def __init__(self, frequency, mins, maxs, phase=0):
        self.mins = np.array(mins)
        self.maxs = np.array(maxs)
        self.frequency = np.array(frequency)
        self.state = np.zeros_like(self.mins).astype(np.float64)
        self.phase = phase
        print self.mins, self.maxs
        
    def update(self, dt):
        self.phase += dt * 2 * np.pi
        self.state = np.sin(self.phase * self.frequency ) * (self.maxs-self.mins) + (self.mins+self.maxs)/2
        
        
class SplineAutomation(object):
    """An automation proxy which moves through points using a TCB spline curve"""
    def __init__(self, pts, rate, loop, tension, continuity, bias):
        self.pts = np.array(pts)
        if len(self.pts.shape)==1:
            self.pts = self.pts[:,None]
        self.rate = rate
        self.loop = loop
        self.spline = CardinalSpline(self.pts, tension, continuity, bias)        
        self.state = np.zeros_like(self.pts[0])
        self.phase = 0
        
    def update(self, dt):
        self.phase += self.rate*dt
        self.state = self.spline(self.phase)
        # loop at end, if required
        if self.phase>=len(self.pts) and self.loop:
            self.phase = 0
            

class RandomAutomation(object):
    """An automation proxy which just Automations between values"""
    def __init__(self, range, rate):
        self.range = np.array(range)
        self.rate = rate
        self.val = SmoothVal(np.random.uniform(self.range[0], self.range[1]), 0)
        self.threshold = np.sum(np.abs((self.range[0]-self.range[1]))) / 100.0
        self.span = np.sum(np.abs(self.range[0]-self.range[1]))
        self.state = self.val.state
        
    def update(self, dt):
        self.val.update(dt)
        if np.sum(np.abs(self.val.state - self.val.target_state))<self.threshold:            
            start, end = self.val.state, np.random.uniform(self.range[0], self.range[1])
            rate = np.sum(abs(end-start)) / (self.span) * self.rate            
            self.val.set_with_time(end, rate)
        self.state = self.val.state
            
    def __str__(self):
        return "range: %s rate: %s val: (%s) " % (self.range, self.rate, self.val)
                        
class AutomationGroup(object):
    """Represent a collection of automation objects"""
    def __init__(self):
        self.automations = {}
        self.attrs = {}
        
    def add(self, name, auto):
        logging.debug("%s, %s" % (name, auto))
        self.automations[name] = copy.deepcopy(auto)
    
    def remove(self, name):
        if name in self.automations:
            del self.automations[name]
            
    def update(self, dt):
        self.attrs = defaultdict(int)
        for auto in self.automations:
            a = self.automations[auto]
            a.update(dt)
            self.attrs[a.attr] += a.state            
            
    def get(self, attr):
        return self.attrs.get(attr, 0)
        
    def __str__(self):
        return "%s" % (self.automations)
                        
class Automation(object):
    """Represents an abstract automation. The appropriate proxy automation
    is created and updated as the automation runs."""
    def __init__(self, spec):
        self.name = spec.get('name', "<unnamed>")
        self.type = spec['type']
        self.attr = spec.get('attr', "time")
        
        
        # random Automation automation
        if self.type=='random':
            par = spec['random']
            self.proxy = RandomAutomation(par['range'], par['rate'])            
            
        # sine wave automation
        if self.type=='sine':
            par = spec['sine']
            self.proxy = SineAutomation(par['frequency'], par['min'], par['max'], par.get('phase', 0))            
            
        # cardinal spline automation
        if self.type=='spline':
            par = spec['spline']
            self.proxy = SplineAutomation(par['points'], rate=par.get('rate', 1.0), loop=par.get('loop', False), 
            tension=par.get('tension', -0.5), continuity=par.get('continuity',0.0), bias=par.get('bias' , 0.0))            
                                         
            
        # allow time modulation
        if 'time' in spec:
            self.time_automation = Automation(spec['time'])
        else:
            self.time_automation = None
        
        self.state = 0
        
    def __str__(self):
        return "%s %s %s (%s)" % (self.name, self.type, self.attr, self.proxy)
        
    def update(self, dt):
        if self.time_automation is None:
            self.proxy.update(dt)
        else:
            self.time_automation.update(dt)
            self.proxy.update(dt * self.time_automation.state)
        self.state = self.proxy.state        
        
                        
class Burst(object):
    """Represents an object which can produce random bursts of
    sound, by triggering sounds from a pool. The burst mode 
    has two states, with different gains, spatial locations and emission rates,
    and switches between them with a simple Markov model."""    
    
    def __init__(self, spec):
        self.name = spec['name']
        self.pool_name = spec['pool']
        self.switching = spec.get('switching', [0.0, 1.0])
        self.enabled = False
        self.rates = []
        self.mins = []
        self.maxs = []
        for state in spec['states']:
            rate = state.get('rate', 0.0)
            self.rates.append(rate)
            min, max = state.get('gain', (0,0))
            self.mins.append(min)
            self.maxs.append(max)
            
        self.min_xyz, self.max_xyz = state.get('space', ((0,0,0), (0,0,0)))                  
        self.gilbert = Gilbert(self.switching[0], self.switching[1])
        
        
    def update(self, dt):
        # do nothing if this is not currently active
        if not self.enabled:
            return None
            
        # switch between modes
        self.gilbert.update(dt)
        state = self.gilbert.state
        # get the emission rate, mean and std. dev gain for this channel
        rate, min, max = self.rates[state], self.mins[state], self.maxs[state]
        
        # correct for sampling rate
        rate = 1-((1-rate)**(dt))                
        
        def pos(ix):
            return np.random.uniform(self.min_xyz[ix], self.max_xyz[ix])
                            
        if random.random()<rate:
            gain = np.random.uniform(min, max)
            gain = np.clip(gain, -120, 0) # make sure gain doesn't exceed 0.0
            x, y, z = pos(0), pos(1), pos(2)
            logging.debug("Triggering burst %s at gain %f at pos %f %f %f", self.name, gain, x, y, z)
            return self.pool_name, gain, (x,y,z)
        else:
            return None
        
        
        
