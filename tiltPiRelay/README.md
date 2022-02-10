# TiltPiRelay
Temp controller relay which uses DS18B20 temp sensors and Tilt hydrometers to monitor temperature, control power relays and log data at adafruit.io.  This is intended for a temp controller and data logger for beer fermentation.  It can control 2 seperate fermentations and also monitor ambient and glycol temperatures.  It's written as a python script and intended to run on a Raspberry Pi.

## Hardware

### Relay Board
I used an off the shelf 4-relay Pi HAT.  The 4 relays allow for 3 states (Heat/Cold/Off) for each of the two monitored channels.

### LCD / Rotary Encoder / LEDs
The rotary encoder used from Adafruit includes a controller and RGB LED which can be accessed by I2C.  The LCD is also I2C and can be daisy chained from the rotary encoder board.  To simplify the wiring, an interposer HAT was created which adds qwiic connectors.

### Temp sensors
There are 5 one-wire-bus temp sensors supported:
  * Channel 1 - Temperature of fermentation 1 (Used for temp control)
  * Channel 2 - Temperature of fermentation 2 (Used for temp control)
  * Ambient - Ambient air temperature (logged and displayed)
  * Glycol - Glycol reserve temperature (logged and displayed)
  * Internal - Internal temperature on the HAT interposer

Each temp sensor is expected to be on it's own bus (GPIO).  This way there is no need to figure out the address of each sensor.  A 3.5mm stereo headset connector is used to make the temperature probes removeable.

### Connector Interposer

## Software

### One time setup
The dependent Python packages need to be available.  One way to do that is with a virtual env:
```
sudo apt-get install python3-dev
python3 -m venv .venv
. ./.venv/bin/activate
pip3 install --upgrade pip setuptools wheel 
pip3 install -r requirements.txt

. ./.venv/bin/activate
CFLAGS="-fcommon"  pip3 install RPi.GPIO
```

### Load w1 busses
The 5 W1 busses need to be started in order so that the script knows which bus is which temp sensor:
```
sudo dtoverlay w1-gpio gpiopin=17 pullup=0
sudo dtoverlay w1-gpio gpiopin=27 pullup=0
sudo dtoverlay w1-gpio gpiopin=23 pullup=0
sudo dtoverlay w1-gpio gpiopin=24 pullup=0
sudo dtoverlay w1-gpio gpiopin=25 pullup=0
```
