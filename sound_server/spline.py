import math, numpy


class CardinalSpline(object):
    """Represent a spline going through a series of points. Evaluable
    at any (fractional) point from 0...len(pts)"""
    
    def __init__(self, pts, tension = -0.5, continuity=0.0, bias=0.0):
        """Create a new spline. Default is with 0.5 tension (Catmull-Rom)"""
        self.pts = pts
        self.tension = tension
        self.continuity = continuity
        self.bias = bias
                
    def __call__(self, t):
        """Evaluate the spline at t (in range 0...len(pts)), floating point"""
        p0 = int(math.floor(t))
        p1 = p0+1
        s = t-p0 # fractional part
        
        # clip range
        if p0<0: 
            p0 = 0
        if p1>=len(self.pts):
            p1 = len(self.pts)-1
        if p0>=len(self.pts):
            p0 = len(self.pts)-1
        
        # compute basis function
        s3 = s**3
        s2 = s**2
        
        h1 = 2*s3 -3 * s2 + 1
        h2 = -2*s3 + 3*s2
        h3  = s3 - 2*s2 + s
        h4 = s3 - s2
        
        # compute tangent vectors
        pm = p0-1
        pp = p1+1
                
        p = self.pts        
        # 0 at ends
        if pm<0:
            t1 = p[p0,:] * 0
        else:
            
            shape1 = (1-self.tension)*(1-self.continuity)*(1+self.bias)*0.5
            shape2 = (1-self.tension)*(1+self.continuity)*(1-self.bias)*0.5
            
            t1 = shape1 * (p[p0,:] - p[pm,:]) + shape2 * (p[p1,:] - p[p0, :])
                           
        if pp>=len(self.pts):
            t2 = p[p0,:] * 0
        else:                
            shape3 = (1-self.tension)*(1+self.continuity)*(1+self.bias)*0.5
            shape4 = (1-self.tension)*(1-self.continuity)*(1-self.bias)*0.5            
            t2 = shape3 * (p[p1,:] - p[p0,:]) + shape4 * (p[pp,:] - p[p1,:])
            
                    
        # interpolate points
        p = p[p0,:] * h1 + p[p1, :] * h2 + t1*h3 + t2*h4
        
        return p
        
            
        
    def __len__(self):
        return len(self.pts)
    

