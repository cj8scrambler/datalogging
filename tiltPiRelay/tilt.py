#!/usr/bin/env python3

"""
  Tilt Hydrometer scanner class

  Based on details from:
  https://kvurd.com/blog/tilt-hydrometer-ibeacon-data-format/
"""

import sys
import os
import time
import logging
import binascii

# BLERadio uses _bleak which require 3.8+
if sys.version_info[0] < 3 or sys.version_info[1] < 8:
  raise Exception("Must be using Python 3.8 or newer")
#pip install adafruit-circuitpython-ble
from adafruit_ble import BLERadio

from struct import unpack
from datetime import datetime, timedelta, timezone
from queue import SimpleQueue

logger = logging.getLogger('tiltpirelay.tilt')

MANUFACTURER_DATA = 0xFF
APPLE_COMPANY_ID = 0x004C
IBEACON_TYPE = 0x02

BLE_SCAN_TIME = 5.0

TILTCOLOR = {
    'A495BB10C5B14B44B5121370F02D74DE': 'RED',
    'A495BB20C5B14B44B5121370F02D74DE': 'GREEN',
    'A495BB30C5B14B44B5121370F02D74DE': 'BLACK',
    'A495BB40C5B14B44B5121370F02D74DE': 'PURPLE',
    'A495BB50C5B14B44B5121370F02D74DE': 'ORANGE',
    'A495BB60C5B14B44B5121370F02D74DE': 'BLUE',
    'A495BB70C5B14B44B5121370F02D74DE': 'YELLOW',
    'A495BB80C5B14B44B5121370F02D74DE': 'PINK',
    '': 'UNKNOWN'
}

class TiltScanner:
  
  def __init__(self):
    self.ble = BLERadio()
    #self.ble._adapter.ble_backend = "bleak"
    self.last = { c: None for c in TILTCOLOR.values() }
    self.q = { c: SimpleQueue() for c in TILTCOLOR.values() }
    self._run = True;

  def HandleBleAdv(self, advertisement_data):
    if MANUFACTURER_DATA in advertisement_data.data_dict:
      mfgdata =  advertisement_data.data_dict[MANUFACTURER_DATA]
      if (len(mfgdata) >= 25):
        (company, subtype) = unpack('<HB', bytes(mfgdata[0:3]))
        if (company == APPLE_COMPANY_ID) and (subtype == IBEACON_TYPE):
          uuid = mfgdata[4:20].hex().upper()
          if uuid in TILTCOLOR:
            color = TILTCOLOR[uuid]
            (temp,sg,tx) = unpack('>HHB', bytes(mfgdata[20:25]))
            datapoint = {'timestamp': datetime.now(timezone.utc).timestamp(),
                         'name': f"tilt-{color}",
                         'temp': temp,
                         'sg': sg / 1000.0,
                         'tx': tx,
                         'rssi': advertisement_data.rssi }
            self.last[color] = datapoint
            self.q[color].put(datapoint)
            logger.debug(f"Added tilt record: {datapoint} size: {self.q[color].qsize()}")
          else:
            logger.info(f"Got data from unknown tilt color uuid: {uuid}")

  def get_last(self, color):
   return self.last[color]

  def get_queue(self, color):
    return  self.q[color]

  def control_thread(self):
    while self._run:
      for advertisement in self.ble.start_scan(timeout=BLE_SCAN_TIME):
        self.HandleBleAdv(advertisement)
      self.ble.stop_scan();
      time.sleep(0.1)

  def end(self):
    self._run = False

if __name__ == "__main__":

    logging.basicConfig(level=logging.DEBUG)

    # Uncomment to set a different BLE log level
    #bleak_log = logging.getLogger("bleak")
    #bleak_log.setLevel(logging.INFO)
    #bleak_log.propagate = True

    # Uncomment to enable HTTP request debugging
    #HTTPConnection.debuglevel = logging.DEBUG
    #requests_log = logging.getLogger("requests.packages.urllib3")
    #requests_log.setLevel(logging.DEBUG)
    #requests_log.propagate = True

    ts = TiltScanner()
    ts.control_thread()
