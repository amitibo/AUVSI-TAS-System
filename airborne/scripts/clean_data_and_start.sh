#!/bin/bash

echo Deleting database...
rm -rf ~/.auvsi_airborne

echo Test camera connection...

# Wait for cannon camera
while [ -z "`lsusb | grep Canon`" ]; do
    echo Not connectd...waiting
    sleep 1
done;

echo Cannon camera connected

echo System starts
start_auvsi.py
