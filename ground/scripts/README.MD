# Running the Ground System

To run the ground system:

    > cd <path to project file>\ground\scripts
    > python start_controller.py
    > python start_ground.py
    > python start_map.py
    > ...

To run the airborne system in simulation mode

    > cd <path to project file>\airborne\scripts
    > python start_auvsi.py --camera simulation --simulate_pixhawk
    

**Note:** In order to run the airborne system in simualation mode you will need
image and flight data from a previous flight.
   
1. Create a data folder with the subfolders ```resized_images``` and ```flight_data```.
2. Place images and flight data in the respective folders.
3. Create an environment variable ```AUVSI_CV_DATA``` pointing to the data folder.
         
## Settings:

### In case the complete system is run on the same computer

In the controller GUI under ````settings``` > ```Network```:

1. IP = 127.0.0.1

In the main GUI under ````settings``` > ```Network```:

1. IP = 127.0.0.1
2. role = primary 
3. IP_CONTROLLER = 127.0.0.1

In the rest of the GUI's (Target, ADLC, etc):

1. IP = 127.0.0.1
2. role = secondary 
3. IP_CONTROLLER = 127.0.0.1

### In case the the airborne system is run on a separate (airborne) computer

In the ```Settintgs``` > ```Network``` of all GUI's:

1. IP = <IP of Airborne Computer>
