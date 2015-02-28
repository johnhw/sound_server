import numpy as np


#sg coefficient computation
def savitzky_golay(window_size=None,order=2):
    if window_size is None:
        window_size = order + 2

    if window_size % 2 != 1 or window_size < 1:
        raise TypeError("window size must be a positive odd number")
    if window_size < order + 2:
        raise TypeError("window size is too small for the polynomial")

    # A second order polynomial has 3 coefficients
    order_range = range(order+1)
    half_window = (window_size-1)//2
    B = np.mat(
        [ [k**i for i in order_range] for k in range(-half_window, half_window+1)] )


    M = np.linalg.pinv(B)
    return M
    

# savitzky-golay polynomial estimator, with optional derivatives
def sg_filter(size, deriv=0, order=4):
    if size%2==0:
        print "Size for Savitzky-Golay must be odd. Adjusting..."
        size = size + 1            
    if order<deriv+1:
        order = deriv+1
    
    sgolay = savitzky_golay(size, order)
    diff = np.ravel(sgolay[deriv, :]) 
    return diff

    
    
class SavitzkyGolay:
    def __init__(self, size, deriv=0, order=4):
        if size%2==0:
            print "Size for Savitzky-Golay must be odd. Adjusting..."
            size = size + 1        
        self.size = size        
        self.deriv = deriv
        if order<deriv+1:
            order = deriv+1
        sgolay = savitzky_golay(size, order)
        diff = np.ravel(sgolay[deriv, :])        
        self.buffer = None
        self.diff = diff
        self.init = False
        
    def new_sample(self, x):
        if self.buffer is None:
            self.buffer = np.ones((self.size,)) * x            
        else:
            self.buffer[0:-1] = self.buffer[1:]
            self.buffer[-1] = x
           
        result = np.sum(self.buffer * self.diff)
        return result
        
    def clear(self):
        self.buffer = None
        
        
                   
