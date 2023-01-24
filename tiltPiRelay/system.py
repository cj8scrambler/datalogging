#!/bin/env python3

import os
#import time
import logging
#import errno
import temp
import time
#import configparser
#import RPi.GPIO as GPIO
#from distutils.util import strtobool
#from glob import glob
from rpi_lcd import LCD
#from time import sleep,now
import board
#from adafruit_seesaw import seesaw, rotaryio, digitalio, neopixel

"""
System display class

 System LCD

  ----------------
 |Ambient: 678.9F |
 |Glycol:   32.4F |
  ----------------

"""

class System:
  
  def __init__(self, display_addr, ambient_tempdev, glycol_tempdev):

    self._ambient = ambient_tempdev
    self._glycol = glycol_tempdev
    self._run = True;

    try:
      self._lcd = LCD(address=display_addr, bus=1, width=16, rows=2)
    except OSError as e:
      logging.warning("LCD [0x{:x}] not available".format(display_addr))
      self._lcd = None

  def system_thread(self):
    while self._run:
      self.update_display()
      time.sleep(1.00)

  def update_display(self):
    lines = ['']*2

    t_string=""
    t=self._ambient.last()
    if (t):
      t_string = "{:.1f}".format(t)
    lines[0] = "{:12s}{:>4s}".format('Ambient:', t_string)

    t_string=""
    t=self._glycol.last()
    if (t):
      t_string = "{:.1f}".format(t)
    lines[1] = "{:12s}{:>4s}".format('Glycol:', t_string)

    logging.debug("Display Update (sys): {:16s}".format(lines[0]))
    logging.debug("Display Update (sys): {:16s}".format(lines[1]))

    if self._lcd:
      self._lcd.text(lines[0], 1)
      self._lcd.text(lines[1], 2)

  def end(self):
    self._run = False
    self._lcd.text("", 1)
    self._lcd.text("", 2)
