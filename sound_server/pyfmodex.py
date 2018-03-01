class Stub:
    def __getattr__(self, attr):
        print(attr)

import sys
s = Stub()
sys.modules["fmodex"] = s