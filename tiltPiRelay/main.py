#!/bin/env python3
import os
import sys
import time
import signal
import queue
import logging
import logging.config
import logging.handlers
import threading
import configparser
sys.path.append('/usr/lib/python3/dist-packages')
import RPi.GPIO as GPIO
from rpi_lcd import LCD
from time import sleep
from adafruit_seesaw import seesaw, rotaryio, digitalio
from queue import SimpleQueue

from temp import Temp
from controller import Controller
from system import System
from tilt import TiltScanner
from adafruit import IOAdafruit

# Time between passes on main event loop
MAIN_LOOP_WAIT_MS = 250

UPDATE_RATE_MS   = 5000

CONFIGFILE = os.path.expanduser('~/.beercntlr.cfg')
UNSET_CREDENTIALS = 'update_this'

TILTCOLORS = [ 'NONE', 'RED', 'GREEN', 'BLACK', 'PURPLE', \
               'ORANGE', 'BLUE', 'YELLOW', 'PINK' ]

"""
The w1 busses need to be added in order:
  sudo dtoverlay w1-gpio gpiopin=23 pullup=0  # CTRL-1  (top left)
  sudo dtoverlay w1-gpio gpiopin=27 pullup=0  # CTRL-2  (top right)
  sudo dtoverlay w1-gpio gpiopin=17 pullup=0  # AMBIENT (top middle)
  sudo dtoverlay w1-gpio gpiopin=24 pullup=0  # GLYCOL  (bottom middle)
  sudo dtoverlay w1-gpio gpiopin=25 pullup=0   # ONBOARD
"""
#I swapped 1 & 2
CTLR_2_TEMP_BUS  = "w1_bus_master1"
CTLR_1_TEMP_BUS  = "w1_bus_master2"
AMBIENT_TEMP_BUS = "w1_bus_master3"
GLYCOL_TEMP_BUS  = "w1_bus_master4"
ONBOARD_TEMP_BUS = "w1_bus_master5"

"""
2 channel temp controller.

Hardware Setup
  Pinout
  ------
  GPIO 2/3 (I2C) (displays, rotarys, LEDs)
  GPIO  4: On Board (OWB)
  GPIO 17: Ambient (OWB)
  GPIO 23: Temp 1 (OWB)
  GPIO 27: Temp 2 (OWB)
  GPIO 24: Glycol (OWB)

  GPIO  6: Heat 2
  GPIO 22: Cool 1
  GPIO 26: Cool 2

3 I2C LCDs:
  1: Control 1
  2: Control 2
  3: System

For each Control channel (2):
  1 I2C 2x16 LCD
  1 Rotary encoder
  1 RGB LED (on rotary encoder board)
"""

HEAT1_GPIO       = 4
COOL1_GPIO       = 22
HEAT2_GPIO       = 6
COOL2_GPIO       = 26

DISP1_ADDR       = 0x26
ROT1_ADDR        = 0x37
DISP2_ADDR       = 0x27
ROT2_ADDR        = 0x36
DISP_SYS_ADDR    = 0x25

# Globals
run = True

c1 = None
thread1 = None

c2 = None
thread2 = None

tilt = None
tilt_thread = None

aio = None
adafruit_thread = None

sysinfo = None
sysinfo_thread = None

def signal_handler(sig, frame):
  global run, thread1, thread2, tilt, tilt_thread, aio, adafruit_thread, c1, c2, sysinfo, sysinfo_thread
  logger.warning("Shutting Down")
  run = False
  if c1:
    c1.end()
  if c2:
    c2.end()
  if sysinfo:
    sysinfo.end()
  if tilt:
    tilt.end()
  if aio:
    aio.end()
  if thread1:
    thread1.join()
    logger.debug("thread 1 done")
  if thread2:
    thread2.join()
    logger.debug("thread 2 done")
  if sysinfo_thread:
    sysinfo_thread.join()
    logger.debug("sysinfo thread done")
  if tilt_thread:
    tilt_thread.join()
    logger.debug("tilt thread done")
  if adafruit_thread:
    adafruit_thread.join()
    logger.debug("adafruit thread done")
  logger.debug("done")

def main():
  global run, thread1, thread2, tilt_thread, aio, adafruit_thread, c1, c2, sysinfo, sysinfo_thread, tilt

  signal.signal(signal.SIGINT, signal_handler)
  signal.signal(signal.SIGTERM, signal_handler)

  config = configparser.ConfigParser()
  config.read(CONFIGFILE)
  logger.debug("Begin")

  # Add default values in case config file was missing/empty
  if 'setpoint' not in config['DEFAULT']:
    # Setup default values
    config['DEFAULT'] = { 'setpoint' : '65.0',
                          'tiltcolor': 'ORANGE',
                          'window': '0.2',
                          'updated': 'False' }
  if 'system' not in config:
    config['system'] = {  'aio_user': UNSET_CREDENTIALS,
                          'aio_key': UNSET_CREDENTIALS,
                          'interval': 60,
                          'updated': 'True' }
  if 'port1' not in config:
    config['port1'] = {}
  if 'port2' not in config:
    config['port2'] = {}

  # Thread to monitor Tilts
  tilt = TiltScanner()
  tilt_thread = threading.Thread(target=tilt.control_thread, daemon=True)
  tilt_thread.start()

  t1 = Temp("temp1", CTLR_1_TEMP_BUS)
  q1 = queue.SimpleQueue()
  c1 = Controller('ctrl-1', config['port1'], HEAT1_GPIO, COOL1_GPIO,
                  t1, tilt, DISP1_ADDR, ROT1_ADDR);

  t2 = Temp("temp2", CTLR_2_TEMP_BUS)
  q2 = queue.SimpleQueue()
  c2 = Controller('ctrl-2', config['port2'], HEAT2_GPIO, COOL2_GPIO,
                  t2, tilt, DISP2_ADDR, ROT2_ADDR);

  # Start Controller UI/control logic
  thread1 = threading.Thread(target=c1.control_thread, daemon=True)
  thread1.start()
  thread2 = threading.Thread(target=c2.control_thread, daemon=True)
  thread2.start()

  t_amb = Temp("ambient", AMBIENT_TEMP_BUS)
  q_amb = queue.SimpleQueue()
  t_gly = Temp("glycol", GLYCOL_TEMP_BUS)
  q_gly = queue.SimpleQueue()

  sysinfo = System(DISP_SYS_ADDR, t_amb, t_gly)
  sysinfo_thread = threading.Thread(target=sysinfo.system_thread, daemon=True)
  sysinfo_thread.start()

  t_int = Temp("internal", ONBOARD_TEMP_BUS)
  q_int = queue.SimpleQueue()

  # Thread to upload data
  if ((config['system']['aio_user'] == UNSET_CREDENTIALS) or
      (config['system']['aio_user'] == UNSET_CREDENTIALS)):
    print(f"Set AIO username / key in {CONFIGFILE} to upload data")
  else:
    aio = IOAdafruit(user=config['system']['aio_user'],
                     key=config['system']['aio_key'],
                     interval=int(config['system']['interval']))
    aio.add_q(c1.q)
    aio.add_q(c2.q)
    aio.add_q(q1)
    aio.add_q(q2)
    aio.add_q(q_amb)
    aio.add_q(q_gly)
    aio.add_q(q_int)
    for q in tilt.q.values():
      aio.add_q(q)
    adafruit_thread = threading.Thread(target=aio.control_thread, daemon=True)
    adafruit_thread.start()

  logger.debug("Staring main loop")
  while run:
    last_time = time.time()

    t1.get_temp(q1)
    t2.get_temp(q2)
    t_amb.get_temp(q_amb)
    t_gly.get_temp(q_gly)
    t_int.get_temp(q_int)

    if config['system'].getboolean('updated') or \
       config['port1'].getboolean('updated') or \
       config['port2'].getboolean('updated'):
      logger.debug("Change found, update configfile")
      config['system']['updated'] = 'False'
      config['port1']['updated'] = 'False'
      config['port2']['updated'] = 'False'
      with open(CONFIGFILE, 'w') as configfile:
        config.write(configfile)

    while (time.time() - last_time) < (MAIN_LOOP_WAIT_MS / 1000.0):
      sleep(0.005)

if __name__ == "__main__":
  logger = logging.getLogger('tiltpirelay')

  LOG_FILENAME = 'debug.log'
  logfile = logging.handlers.RotatingFileHandler(
              LOG_FILENAME, maxBytes=20971520, backupCount=0)
  logfile.setLevel(logging.DEBUG)

  console = logging.StreamHandler()
  console.setLevel(logging.INFO)

  formatter = logging.Formatter('%(asctime)s - %(name)s:%(lineno)d %(levelname)s - %(message)s')
  logfile.setFormatter(formatter)
  console.setFormatter(formatter)

  logger.addHandler(logfile)
  logger.addHandler(console)

  logger.setLevel(logging.DEBUG)
  logging.getLogger("tiltpirelay.controller").setLevel(logging.INFO)
  logging.getLogger("tiltpirelay.system").setLevel(logging.INFO)
  logging.getLogger("tiltpirelay.temp").setLevel(logging.INFO)
  logging.getLogger("tiltpirelay.tilt").setLevel(logging.INFO)
  logging.getLogger("tiltpirelay.adafruit").setLevel(logging.DEBUG)

  main()
