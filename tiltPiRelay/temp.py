#!/bin/env python3

import time
import sys
import logging
import statistics
import RPi.GPIO as GPIO
from datetime import datetime, timezone
from glob import glob

"""
Temp reader class

Handles reading temp from one-wire bus temp sensor.  Assumes
a single temp sensor on the bus.

"""

INTERVALS_MEDIAN_SIZE = 5

class Temp:
  
  def __init__(self, name, w1_bus):
    self._bus = w1_bus
    self._name = name
    self._file = None
    self._last_temp  = None
    self._last_time  = None
    self._interval = None
    self._intervals = []

    self.get_temp()

  def get_interval(self):
    if self._interval:
      return self._interval
    if (len(self._intervals)):
      median = statistics.median(self._intervals)
      if len(self._intervals) >= INTERVALS_MEDIAN_SIZE:
          self._interval = median
      return median
    return sys.maxsize

  def get_temp(self, q = None):
    now = time.time()
    if self._last_time and len(self._intervals) < INTERVALS_MEDIAN_SIZE:
      self._intervals.append(now - self._last_time)
    self._last_time = now
    if self._file is None:
      try:
        self._file = glob('/sys/bus/w1/devices/' + self._bus + '/28-*/temperature')[0]
      except IndexError as e:
        logging.warning("No temp sensor found on bus {}".format(self._bus))
        self._last_temp  = None
        return

    try:
      f = open(self._file, 'r')
    except OSError as e:
      logging.warning("Temp sensor removed on bus {}".format(self._bus))
      self._file = None
      self._last_temp  = None
      return

    lines = f.readlines()
    f.close()

    # value is in thousandths of degrees C; convert to decimal F
    if (len(lines)):
      self._last_temp = (float(lines[-1]) * 9/5000) + 32.0
      logging.debug("Read temp on {}: {} F".format(self._bus, self._last_temp))

      if q:
        q.put({'timestamp': datetime.now(timezone.utc).timestamp(),
               'name': self._name,
               'temp': self._last_temp})
      return self._last_temp
    return None

  def last(self):
    return self._last_temp
