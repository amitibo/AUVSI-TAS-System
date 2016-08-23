'''
start_map
=========

Stitch the images based on their flight data.
'''
from AUVSIground.gui_map import MapApp


def start_gui():
    MapApp().run()


if __name__ == '__main__':
    #
    # Start the GUI
    #
    start_gui()
