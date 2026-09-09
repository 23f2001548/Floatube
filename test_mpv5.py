import sys, os
_script_dir = os.path.abspath('.')
os.environ['PATH'] = _script_dir + os.pathsep + os.environ['PATH']

import mpv
import time

p = mpv.MPV()
@p.event_callback("end-file")
def ev(event):
    print("Event dict:", event)
    # print all properties of event object
    try:
        if hasattr(event, 'as_dict'):
            print(event.as_dict())
        else:
            print(dir(event))
            if hasattr(event, 'event'):
                print("inner:", dir(event.event))
                print(event.event)
    except Exception as e:
        print(e)
        
p.play('nonexistent.mp3')
time.sleep(1)
p.stop()
time.sleep(1)
