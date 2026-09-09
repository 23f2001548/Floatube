import sys, os
_script_dir = os.path.abspath('.')
os.environ['PATH'] = _script_dir + os.pathsep + os.environ['PATH']

import mpv
import time

p = mpv.MPV()
@p.event_callback("end-file")
def ev(event):
    print(event.as_dict())
        
filepath = r'C:\Users\Gaura\Music\Floatube_Downloads\KALYANI (Remix) - ARJN KDS FIFTY4 Shreya Ghoshal.m4a'
p.play(filepath)
time.sleep(1)
p.stop()
time.sleep(1)
