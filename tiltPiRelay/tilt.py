#!/usr/bin/env python3

"""
  Tilt Hydrometer scanner class

  Uses bleak library to read any available Tilt Hydrometer data
"""

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from struct import unpack
from datetime import datetime, timedelta, timezone
from queue import SimpleQueue
#from collections import deque
import asyncio
import logging

## Group name to store all feeds in
#GROUP_NAME = 'Tilt Hydrometers'

APPLE_COMPANY_ID = 0x004C
IBEACON_TYPE = 0x02

TILTCOLOR = {                                    \
    'A495BB10C5B14B44B5121370F02D74DE': 'red',   \
    'A495BB20C5B14B44B5121370F02D74DE': 'green', \
    'A495BB30C5B14B44B5121370F02D74DE': 'black', \
    'A495BB40C5B14B44B5121370F02D74DE': 'purple',\
    'A495BB50C5B14B44B5121370F02D74DE': 'orange',\
    'A495BB60C5B14B44B5121370F02D74DE': 'blue',  \
    'A495BB70C5B14B44B5121370F02D74DE': 'yellow',\
    'A495BB80C5B14B44B5121370F02D74DE': 'pink' }


class TiltScanner:
  
  def __init__(self):
    self.scanner = BleakScanner()
    self.scanner.register_detection_callback(HandleBleAdv)
    self.last = { c: None for c in TILTCOLOR.values() }
    self.q = { c: SimpleQueue() for c in TILTCOLOR.values() }

  def HandleBleAdv(self, device: BLEDevice, advertisement_data: AdvertisementData):
    if advertisement_data.manufacturer_data:
      for company in advertisement_data.manufacturer_data:
        data = bytes(advertisement_data.manufacturer_data[company])
        if (company == APPLE_COMPANY_ID) and (data[0] == IBEACON_TYPE):
          uuid = data[2:18].hex().upper()
          if uuid in TILTCOLOR:
            color = TILTCOLOR[uuid]
            (major,minor,tx) = unpack('>HHB', bytes(data[18:23]))
            datapoint = {'timestamp': datetime.now(timezone.utc).isoformat(), \
                         'color': color,                           \
                         'temp': major,                            \
                         'sg': minor / 1000.0,                     \
                         'tx': tx,                                 \
                         'rssi': device.rssi }
            self.last[color] = datapoint
            self.q[color].put(datapoint)
            logging.debug("Recorded {} data: {}".format(color, datapoint))

  def startScan():
    self.scanner.start()

  def stopScan():
    self.scanner.stop()

  def popData(color):
    try:
      self.q[color].get()
    except Queue.Empty:
      return None

  def last(color):
    return self.last[color]

#  async def control_thread():
  def control_thread():
    while True:
        await scanner.start()
        await asyncio.sleep(5)
        await scanner.stop()

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    # Uncomment to set a different BLE log level
    bleak_log = logging.getLogger("bleak")
    bleak_log.setLevel(logging.INFO)
    bleak_log.propagate = True

    # Uncomment to enable HTTP request debugging
    #HTTPConnection.debuglevel = logging.DEBUG
    #requests_log = logging.getLogger("requests.packages.urllib3")
    #requests_log.setLevel(logging.DEBUG)
    #requests_log.propagate = True

    asyncio.run(main())
