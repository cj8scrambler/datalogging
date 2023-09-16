#!/bin/bash
set -e

LOAD_CMDS=("dtoverlay w1-gpio gpiopin=23 pullup=0",
"dtoverlay w1-gpio gpiopin=27 pullup=0",
"dtoverlay w1-gpio gpiopin=17 pullup=0",
"dtoverlay w1-gpio gpiopin=24 pullup=0",
"dtoverlay w1-gpio gpiopin=25 pullup=0")

if [[ $1 == "load" ]]
then
  if [[ $(lsmod | grep -c w1_gpio) -eq 0 ]]
  then
    echo "Loading modules"
    modprobe w1_gpio
  fi

  for ((i = 0; i < ${#LOAD_CMDS[@]}; i++))
  do
    BUS="/sys/devices/w1_bus_master$(($i+1))"
    if [[ ! -d ${BUS} ]]
    then
      echo "Setup ${BUS} (${LOAD_CMDS[$i]})"
      ${LOAD_CMDS[$i]}
    fi
  done
elif [[ $1 == "unload" ]]
then
  if [[ $(compgen -G "/sys/bus/w1/devices/28-*" | wc -l) -ne 0 ]]
  then
    for DEV in $(ls -d /sys/bus/w1/devices/28-*)
    do
      RP=$(realpath ${DEV})
      ID=$(basename ${RP})
      BUS=$(basename $(dirname ${RP}))

      echo "Removing device ${ID} from ${BUS}"
      # Disable search on that bus:
      echo 0 > /sys/devices/${BUS}/w1_master_search
      # Remove the device
      echo ${ID} > /sys/devices/${BUS}/w1_master_remove
    done
  fi

  if [[ $(lsmod | grep -c w1_gpio) -ne 0 ]]
  then
    echo "Unloading modules"
    # remove the modules
    rmmod w1_gpio w1_therm wire
  fi
else
  echo "Usage: $(basename $0) load|unload"
fi
