# Simulation Mode

To run the airborne in simulation mode on single computer:
```cd <path to project file>\ground\scripts```

    1. activate GUI: ```python start_ground.py```
    2. activate MAP: ```python start_map.py```

```cd <path to project file>\airborne\scripts```

    1. activate airborne: ```python start_auvsi.py --camera simulation --simulate_pixhawk```

**Note:** Before running the airborne system you need to setup images and flight
data:
   
    1. Create a folder data folder with to subfolders ```resized_images``` and
       ```flight_data```
    2. Place images and flight in the respective folders.
    3. Create an environment variable ```AUVSI_CV_DATA``` pointing to the data
       folder.
         
## Settings:

### In case the complete system is run on the same computer

In GUI > settings >

    1. role = primary 
    2. IP = local host = 127.0.0.1

In Map > settings >

    1. role = secondery 
    2. IP = 127.0.0.1
    3. IP_PRIMERY = 127.0.0.1

### In case the the airborne system is run on a dedicated computer

In GUI > settings >

    1. role = primary
    2. IP = local host = 192.168.1.101

In Map > settings >
    
    1. role = secondery 
    2. IP = 192.168.1.201
    3. IP_PRIMERY = 192.168.1.101
    
