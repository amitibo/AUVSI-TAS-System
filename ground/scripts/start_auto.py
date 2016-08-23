'''
start_auto
=========

Start the automatic identification GUI.
'''
from AUVSIground.gui_auto import AutoApp


def start_gui():
    AutoApp().run()


if __name__ == '__main__':
    #
    # Start the GUI
    #
    start_gui()
