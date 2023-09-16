#!/bin/bash

#export PATH=${PATH}:/home/zobel/.local/bin
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

if [[ ! -d /sys/devices/w1_bus_master1 || \
      ! -d /sys/devices/w1_bus_master2 || \
      ! -d /sys/devices/w1_bus_master3 || \
      ! -d /sys/devices/w1_bus_master4 || \
      ! -d /sys/devices/w1_bus_master5 ]]
then
  echo "Error: One Wire Bus interfaces are not setup."
  echo "       Run the following to create them (in order):"
  echo "dtoverlay w1-gpio gpiopin=17 pullup=0"
  echo "dtoverlay w1-gpio gpiopin=27 pullup=0"
  echo "dtoverlay w1-gpio gpiopin=23 pullup=0"
  echo "dtoverlay w1-gpio gpiopin=24 pullup=0"
  echo "dtoverlay w1-gpio gpiopin=4 pullup=0"
  exit -1
fi


cd ${SCRIPT_DIR}
. ./.venv/bin/activate
python3.8 ./main.py
