![The "ATHENE" Drone](imgs/athene.jpg)
# AUVSI Image Processing Software

The AUVSI Image Procssing Software contains the software developed for the
[AUVSI SUAS competition](http://www.auvsi-suas.org/) for the image processing
tasks.
The sofware was developed and used by the TAS team during the
[2015](http://www.auvsi-suas.org/competitions/2015/) and 
[2016](http://www.auvsi-suas.org/competitions/2016/) competitions.
The software is made of three sub-projects:

  * The software of the airborne computer.
  * The software that runs on the ground station.
  * Image processing algorithms.

Both the airborne and ground station software make use of the image processing
sub-project.
The software is written completely in python.

## Airborne System

The airborne platform used in both the 2015 and 2016 competitions is the
[ODROID XU3](http://www.hardkernel.com/main/products/prdt_info.php?g_code=G140448267127)
running xubunutu 14.04.

### Prerequisits

* **python** - Install using ```sudo apt-get install python```
* **opencv** - Install using ```sudo apt-get install python-opencv```
* **twisted** - Install using ```sudo apt-get install python-twisted```
* **scikit-image** - Install using ```sudo apt-get install python-skimage```
* **sortedcontainers** - Install using ```sudo -H pip install sortedcontainers```
* **txzmq** - Install using ```sudo -H pip install txzmq```
* **pyserial** - Install using ```pip install pyserial```

The camera used in the 2016 competition was a Nikon a6000. The TAS team
developed a custom driver for the camera. The driver is a separate
project and not included in this distribution. Nonetheless it should be
relatively simple to adapt the code to use a different camera.

To help in development and practice, a camera **Simulation** mode was developed.
In this mode the system replays previously captured images and flight data and
thus imitates a camera. This way the complete software can be run on a
single computer.
To use the simulation mode, the following packages should also be
installed:

* **freetype** - Install using ```sudo apt-get install libfreetype6```
* **aggdraw** - Install from source (preferably from svn) set the
  variable FREETYPE_ROOT = "/usr/" in the setup.py file.
* **PIL**
* **exifread**- Install with ```pip install exifread```
* **pyqrcode** - Install with ```pip install pyqrcode```
* **pypng** - Install with ```pip install pypng```

You will also need to place some *True Type* fonts in the
```image_processing/AUVSIcv/resources/fonts```. This fonts are used for
generating *fake* targets (not included in this distribution due to copyright).

### Installation

    > cd auvis/airborne
    > python setup.py install
    > cd ../image_processing
    > python setup.py install

## Ground platform and Image Processing project

### Prerequisits

* **Python** - Recommended to install using a distibution like
  [Anaconda](https://www.continuum.io/downloads).
* **twisted** - Install using ```conda install twisted```
* **opencv** - Install from [Unofficial python binaries](http://www.lfd.uci.edu/~gohlke/pythonlibs/).
  Tested with version >= 2.4.10
* **pygame** - Install from [Unofficial python binaries](http://www.lfd.uci.edu/~gohlke/pythonlibs/).
* **kivy** - Install from [Unofficial python binaries](http://www.lfd.uci.edu/~gohlke/pythonlibs/).
* **aggdraw** - (used for the image processing project):
  Install from [Unofficial python binaries](http://www.lfd.uci.edu/~gohlke/pythonlibs/).
* **exifread** - Install with ```pip install exifread```.
* **pyqrcode** - Install with ```pip install pyqrcode```.
* **pypng** - Install with ```pip install pypng```.

### Installation

    > cd auvis/ground
    > python setup.py install
    > cd ../image_processing
    > python setup.py install

## How to Use

* Start the ariborne system using one of the script inside ```airborne/scripts```
* Start the ground system using the scripts in ```ground/scripts```

## License

MIT License (see `LICENSE` file).
