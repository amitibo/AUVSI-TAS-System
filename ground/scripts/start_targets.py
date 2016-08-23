'''
start_targets
=========

Start the target selection GUI.
'''
from AUVSIground.gui_targets import TargetsApp


def start_gui():
    TargetsApp().run()


if __name__ == '__main__':
    #
    # Start the GUI
    #
    start_gui()
