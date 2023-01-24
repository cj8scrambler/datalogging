#!/bin/env python3

import os
import time
import logging
import errno
import temp
import configparser
import RPi.GPIO as GPIO
from distutils.util import strtobool
from queue import SimpleQueue
#from glob import glob
from rpi_lcd import LCD
#from time import sleep,now
from datetime import datetime, timezone
import board

from adafruit_seesaw import seesaw, rotaryio, digitalio, neopixel

"""
Temp controller class

Controller LCD                             System LCD
  Idle
 ----------------                           ----------------
|123.4/567.8 HEAT|  HEAT/COOL              |Ambient: 678.9F |
|Tilt: 124.3 F   |  124.4 F / 1.064        |Glycol:   32.4F |
 ----------------                           ----------------

  First press;
 ----------------
|Set Setpoint:   |
|  123.4 F       |
 ----------------

  Next press;
 ----------------
|Set Tilt Color: |
|  ORANGE        |
 ----------------

  Next press;
 ----------------
|Set window:     |
|  0.2 F         |
 ----------------

Software controller states:
    COOL: temp > setpoint+window: 
    HEAT: temp < setpoint-window: 
    SET:  set setpoint
    TILT: set Tilt color
    WIND: set window (0.0 - 5.0)
"""


RED = (255, 0, 0)
YELLOW = (255, 150, 0)
GREEN = (0, 255, 0)
CYAN = (0, 255, 255)
BLUE = (0, 0, 255)
PURPLE = (180, 0, 255)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

WINMIN = 0.0
WINMAX = 5.0

STATES = ['IDLE', 'SET', 'TILT', 'WIND']
MODES = ['INVALID', 'HEAT', 'COOL', 'OFF']
TILTCOLORS = [ 'NONE', 'RED', 'GREEN', 'BLACK', 'PURPLE', \
               'ORANGE', 'BLUE', 'YELLOW', 'PINK' ]

IDLE_TIMEOUT = 4
#TOGGLE_TIME  = 2
EVENT_LOOP_WAIT_MS = 100

class Controller:
  
  def __init__(self, name, config, heat_gpio, cool_gpio, \
               tempdev, tiltdev, display_addr, rot_addr):

    self._name = name
    self._config = config
    self._state = STATES.index('IDLE')
    self._mode = MODES.index('INVALID')
    self._goidle = time.time()
    self._temp = tempdev
    self._tilt = tiltdev
    self._last_disp_temp = None
    self._last_mode_update = 0
    self._run = True;
    self._ = True;
    self.q = SimpleQueue()


    # Temp placeholders
    self._tilt_temp = None
    self._tilt_sg = None

    if GPIO.getmode() != GPIO.BCM:
        GPIO.setmode(GPIO.BCM)
    GPIO.setup([heat_gpio, cool_gpio], GPIO.OUT)
    GPIO.output([heat_gpio, cool_gpio], GPIO.LOW)
    self._heat_gpio = heat_gpio
    self._cool_gpio = cool_gpio

    try:
      self._lcd = LCD(address=display_addr, bus=1, width=16, rows=2)
    except OSError as e:
      logging.warning("LCD [0x{:x}] not available".format(display_addr))
      self._lcd = None

    try:
      rot_led_board = seesaw.Seesaw(board.I2C(), addr=rot_addr)
      rot_led_board.pin_mode(24, rot_led_board.INPUT_PULLUP)
      self._button = digitalio.DigitalIO(rot_led_board, 24)
      self._last_but = not self._button.value
      self._rot = rotaryio.IncrementalEncoder(rot_led_board)
      self._last_pos = -self._rot.position # - makes CW increment
      self._pixel = neopixel.NeoPixel(rot_led_board, 6, 1)
      self._pixel.brightness = 0.1
      self._pixel.fill(YELLOW)
    except ValueError as e:
      logging.warning("Rotary/LED [0x{}] not available".format(display_addr))
      self._button = None
      self._last_but = False
      self._rot = None
      self._last_pos = 0
      self._pixel = None

    self.update_mode()

  def update_mode(self):
    old_mode = self._mode
    if self._temp.last() is None:
      self._mode = MODES.index('INVALID')
      GPIO.output(self._heat_gpio, 0)
      GPIO.output(self._cool_gpio, 0)
      self.q.put({'timestamp': datetime.now(timezone.utc).timestamp(), \
                  'name': f"{self._name}",               \
                  'setpoint': float(self._config['setpoint']),
                  'window': float(self._config['window']),
                  'heat': 0,
                  'cool': 0})
      if self._pixel:
          self._pixel.fill(YELLOW)
    elif self._temp.last() > (float(self._config['setpoint']) + \
                              float(self._config['window'])):
      self._mode = MODES.index('COOL')
      GPIO.output(self._heat_gpio, 0)
      GPIO.output(self._cool_gpio, 1)
      self.q.put({'timestamp': datetime.now(timezone.utc).timestamp(), \
                  'name': f"{self._name}",               \
                  'setpoint': float(self._config['setpoint']),
                  'window': float(self._config['window']),
                  'heat': 0,
                  'cool': 100})
      if self._pixel:
          self._pixel.fill(BLUE)
    elif self._temp.last() < (float(self._config['setpoint']) - \
                              float(self._config['window'])):
      self._mode = MODES.index('HEAT')
      GPIO.output(self._cool_gpio, 0)
      GPIO.output(self._heat_gpio, 1)
      self.q.put({'timestamp': datetime.now(timezone.utc).timestamp(), \
                  'name': f"{self._name}",               \
                  'setpoint': float(self._config['setpoint']),
                  'window': float(self._config['window']),
                  'heat': 100,
                  'cool': 0})
      if self._pixel:
          self._pixel.fill(RED)
    else:
      self._mode = MODES.index('OFF')
      GPIO.output(self._heat_gpio, 0)
      GPIO.output(self._cool_gpio, 0)
      self.q.put({'timestamp': datetime.now(timezone.utc).timestamp(), \
                  'name': f"{self._name}",               \
                  'setpoint': float(self._config['setpoint']),
                  'window': float(self._config['window']),
                  'heat': 0,
                  'cool': 0})
      if self._pixel:
          self._pixel.fill(BLACK)

    # return True if state changed
    return old_mode != self._mode

  def update_display(self):
    lines = ['']*2

    if STATES[self._state] == 'INVALID':
      lines[0] = "ERROR: MISSING"
      lines[1] = "TEMP SENSOR"

    elif STATES[self._state] == 'IDLE':
      t = self._temp.last()
      self._last_disp_temp = t
      if t is None:
        temp='missing'
      else:
        temp = "{:.1f}/{:.1f}".format(t, float(self._config['setpoint']))
      lines[0] = "{:12s}{:4s}".format(temp, MODES[self._mode])
      if self._config['tiltcolor'] != 'NONE' and \
         self._tilt_temp != None and \
         self._tilt_sg != None:
        tilt_temp = "{:.1f}".format(self._tilt_temp)
        tilt_sg = "{:.3f}".format(self._tilt_sg)
        lines[1] = "T: {:5s}  {:5s}".format(tilt_temp, tilt_sg)
#        if (time.time() % (2*TOGGLE_TIME)) >= TOGGLE_TIME:
#          lines[1] = "Tilt: {} F".format(self._tilt_temp)
#        else:
#          lines[1] = "Tilt: {} SG".format(self._tilt_sg)
  
    elif STATES[self._state] == 'SET':
      lines[0] = "Set Setpoint:"
      lines[1] = "  {:.1f} F".format(float(self._config['setpoint']))

    elif STATES[self._state] == 'TILT':
      lines[0] = "Set Tilt Color:"
      lines[1] = "  {}".format(self._config['tiltcolor'])

    elif STATES[self._state] == 'WIND':
      lines[0] = "Set Window:"
      lines[1] = "  {:.1f} F".format(float(self._config['window']))

    else:
      logging.error("Display update unknown state: {}".format(self._state))

    logging.debug("Display Update (ctlr-{}): {:16s}".format(self._temp._bus, lines[0]))
    logging.debug("Display Update (ctlr-{}): {:16s}".format(self._temp._bus, lines[1]))
    if self._lcd:
      self._lcd.text(lines[0], 1)
      self._lcd.text(lines[1], 2)

  def is_idle(self):
    return (time.time() > self._goidle)

  def control_thread(self):
    while self._run:
      begin_time = time.time()
      uichange = False
      display_update = False

      # Run updates at the same interval that temp is being queried
      if (begin_time - self._last_mode_update) > self._temp.get_interval():
        self._last_mode_update = begin_time
        uichange = self.update_mode()

      if self._button:
        # I2C access fails sometimes; ignore those
        try:
            but = not self._button.value
        except OSError as e:
            logging.error("Button read failure: {}".format(e))
            continue
      else:
        but = self._last_but

      if self._rot:
        try:
            pos = -self._rot.position #negative makes CW go up
        except OSError as e:
            logging.error("Rotary read failure: {}".format(e))
            continue
      else:
        pos = self._last_pos

      # Handle button press
      if not self._last_but and but:
        self._state = (self._state + 1) % len(STATES)
        logging.debug("Button press; new state: {}".format(STATES[self._state]))
        uichange = True

      # Handle rotation
      # TODO: maybe add some acceleration scaling
      elif self._last_pos != pos:
        logging.debug("Rotation: {}".format(pos - self._last_pos))
        if STATES[self._state] == 'SET':
          self._config['setpoint'] = str(float(self._config['setpoint']) + \
                                         (pos - self._last_pos) / 10.0)
          self._config['updated'] = 'True'
          uichange = True
          logging.info("New setpoint: {}".format(self._config['setpoint']))
        elif STATES[self._state] == 'TILT':
          new_i = (TILTCOLORS.index(self._config['tiltcolor']) + \
                   (pos - self._last_pos)) % len(TILTCOLORS)
          self._config['tiltcolor'] = TILTCOLORS[new_i]
          self._config['updated'] = 'True'
          uichange = True
          logging.info("New Tilt Color: {}".format(self._config['tiltcolor']))
        elif STATES[self._state] == 'WIND':
          new_w = float(self._config['window']) + (pos - self._last_pos)/10.0
          new_w = max(WINMIN, min(WINMAX, new_w))
          if new_w != float(self._config['window']):
            self._config['window'] = str(new_w)
            self._config['updated'] = 'True'
            uichange = True
            logging.info("New Window: {}".format(self._config['window']))
  
      # UI change resets idle timeout
      if uichange:
        self._goidle = time.time() + IDLE_TIMEOUT
        display_update = True

      # Check for temp change in IDLE
      if (self._state == STATES.index('IDLE')) and \
         (self._last_disp_temp != self._temp.last()):
        logging.debug("Temp Change (ctrl-{}): {} -> {}".format(self._temp._bus, self._last_disp_temp, self._temp.last()))
        display_update = True

      if display_update:
        self.update_display()

      self._last_but = but
      self._last_pos = pos

      # Lower Priority Work
      if (time.time() - begin_time) < (EVENT_LOOP_WAIT_MS / 2000.0):
        # Update Tilt data
        if self._config['tiltcolor'] != 'NONE' and \
           self._tilt is not None:
          last = self._tilt.get_last(self._config['tiltcolor'])
          # TODO: check timestamp to see if it's recent enough
          if last is not None:
            self._tilt_temp = last['temp']
            self._tilt_sg = last['sg']

        # Check for idle timeout
        if self.is_idle() and self._state != STATES.index('IDLE'):
          logging.debug("Idle timeout")
          self._state = STATES.index('IDLE')
          display_update = True

      while (time.time() - begin_time) < (EVENT_LOOP_WAIT_MS / 1000.0):
        time.sleep(0.01)

  def end(self):
    self._run = False
    self._pixel.fill(BLACK)
    self._lcd.text("", 1)
    self._lcd.text("", 2)
