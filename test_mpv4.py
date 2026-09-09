import sys
import os

_script_dir = os.path.abspath('.')
os.environ['PATH'] = _script_dir + os.pathsep + os.environ['PATH']

import mpv
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

app = QApplication(sys.argv)
player = mpv.MPV(ytdl=False, log_handler=print)

def run_test():
    filepath = r'C:\Users\Gaura\Music\Floatube_Downloads\KALYANI (Remix) - ARJN KDS FIFTY4 Shreya Ghoshal.m4a'
    
    @player.property_observer('core-idle')
    def obs(_name, value):
        print(f"idle: {value}")
        
    @player.property_observer('paused-for-cache')
    def obs2(_name, value):
        print(f"cache pause: {value}")

    print("playing...")
    player.play(filepath)
    
QTimer.singleShot(0, run_test)
QTimer.singleShot(3000, lambda: [print("Timeout"), app.quit()])
sys.exit(app.exec())
