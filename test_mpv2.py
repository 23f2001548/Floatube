import sys
import os
import time

_script_dir = os.path.abspath('.')
os.environ['PATH'] = _script_dir + os.pathsep + os.environ['PATH']

from services import AudioEngine
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

app = QApplication(sys.argv)
engine = AudioEngine()

def run_test():
    filepath = r'C:\Users\Gaura\Music\Floatube_Downloads\KALYANI (Remix) - ARJN KDS FIFTY4 Shreya Ghoshal.m4a'
    
    def on_state(s):
        print(f'State changed: {s}')
        if s == 'playing':
            app.quit()
            
    engine.state_changed.connect(on_state)
    engine.error.connect(lambda e: print(f'Error: {e}'))
    
    # Try forward slashes
    engine.play(filepath.replace('\\', '/'))
    
QTimer.singleShot(0, run_test)
QTimer.singleShot(3000, lambda: [print("Timeout"), app.quit()])

sys.exit(app.exec())
