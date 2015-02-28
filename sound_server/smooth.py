import numpy as np
import timeit

class WallTimer(object):
    """Accurate cross-platform wall timer"""
    def __init__(self):
        self.wall_clock = timeit.default_timer
        self.reset()
        
    def time(self):
        return self.wall_clock() - self.start_time
        
    def reset(self):
        self.start_time = self.wall_clock()            

        
class SmoothVal(object):
    """Represents a scalar or vector value which smoothly
    interpolates to a new state, using either exponential or
    linear smoothing."""
    def __init__(self, init_state, init_time=0.01, linear=False, overshoot=0):
        self.state= init_state
        self.target_state = init_state
        self.linear = linear
        self.time = init_time
        self.init_state = self.state
        self.t =0 
        self.update_coeff()
        self.overshoot = overshoot
        self.overshot = False
        
    def update_coeff(self):
        if self.time!=0:
            self.coeff = 2**(-3.0/self.time)    
        else:
            self.coeff = 0
            
    @property
    def complete(self):
        """Return true if the state is at least 90% complete"""
        return self.state>0.9
        
    def set_time(self, time):
        """Set the interpolation time"""
        self.time = time
        self.update_coeff()
        
    def set(self, state):
        """Set the new target state"""
        self.target_state = state
        self.init_state = self.state
        self.t = 0
        
    def set_with_time(self, state, time):
        if time==0:
            self.jump(state)
        else:
            self.set(state)
            self.set_time(time)
        
    def jump(self, state):
        """Jump to the new target state immediately"""
        self.state = state
        self.init_state = self.state
        self.target_state = state
        self.t = 0
        self.time = 0
                
        
    def update(self, dt):
        """Update by dt seconds. Changes self.state"""
        if self.overshoot>0 and not self.overshot:
            target = self.target_state * self.overshoot            
            if abs(self.state-target)<(self.state*self.overshoot/10.0):
                self.overshot = True
        else:
            target = self.target_state        
        
        if self.linear:
            a = np.clip(self.t / (self.time+1e-8), 0, 1)
            self.state = (1-a) * self.init_state + (a)*target
        else:
            a = self.coeff ** dt
            self.state = a*self.state + (1-a)*target
        self.t += dt
        
    def __repr__(self):
        return "State: %s InitState: %s Time: %f t: %f Target:%s" % (self.state, self.init_state, self.time, self.t, self.target_state)
        
    def __str__(self):
        return self.__repr__()
        
        
def test_smooth_val():
    s = SmoothVal(0.0, 1.0)
    sl = SmoothVal(0.0, 1.0, linear=True)
    for ts in [1.0]:
        for target in [1.0]:
            print
            print "Time: %.2f, target %.2f" % (ts, target)
            print
            s.set_time(ts)
            sl.set_time(ts)
            s.set(target)
            sl.set(target)
            t = 0
            for i in range(50):
                s.update(0.01)
                sl.update(0.01)
                print t, s.state, sl.state
                t += 0.1

if __name__=="__main__":
    test_smooth_val()