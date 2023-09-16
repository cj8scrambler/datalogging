import time
import requests
import logging
from datetime import datetime, timezone
from collections import defaultdict
from Adafruit_IO import Client, Feed, Group, errors
from queue import SimpleQueue


"""
IO.Adafruit reporter class

Reports data points from queues to io.adafruit.com

"""

logger = logging.getLogger('tiltpirelay.adafruit')
DEFAULT_REPORT_INTERVAL_S = 55
DEFAULT_GROUP_NAME='garage'

class IOAdafruit:
  
  def __init__(self, user, key, interval=DEFAULT_REPORT_INTERVAL_S, group=DEFAULT_GROUP_NAME):
    self._user = user
    self._key = key
    self._interval = interval
    self._group = group
    self._run = True
    self._qs = []

  def end(self):
    self._run = False

  def add_q(self, q):
    self._qs.append(q)

  def control_thread(self):
    aio = Client(self._user, self._key)
    #aio.set_timeout(30)
    feeds = {}
    last_update = defaultdict(lambda: 0)

    try:
      g = aio.groups(self._group)
    except errors.RequestError:
      logger.warning(f"Creating AIO group: {self._group}")
      g = aio.create_group(Group(name=self._group))
    except requests.exceptions.ConnectionError:
      logger.error("  Failed to query AIO groups (connection error)")
    except requests.exceptions.ReadTimeout:
      logger.error("  Failed to query AIO groups (timeout)")

    for f in g.feeds:
      feeds[f.name] = f

    while self._run:
      for i,q in enumerate(self._qs):
        if not q.empty():
          data = q.get()
          name = data['name']
          delta = data['timestamp'] - last_update[name]
          if delta > self._interval:
            logger.info(f"Reporting data [delta: {delta}]: {data} (Queue-{i} size: {q.qsize()})")
            for k in data:
              if k == 'name' or k == 'timestamp':
                continue
              feedkey = name + '-' + k
              if not feedkey in feeds:
                logger.warning(f"  Creating new feed: {feeds[feedkey].key}")
                feeds[feedkey] = aio.create_feed(Feed(name=feedkey), group_key=self._group)
              try:
                aio.send(feeds[feedkey].key, data[k])
                last_update[name] = data['timestamp']
                logger.debug(f"  Sent '{data[k]}' to {feeds[feedkey].key}")
              except errors.RequestError:
                logger.error("  Failed to send {feedkey} data (request error)")
                time.sleep(5)
                continue
              except requests.exceptions.ConnectionError:
                logger.error("  Failed to send {feedkey} data (connection error)")
                time.sleep(5)
                continue
              except requests.exceptions.ReadTimeout:
                logger.error("  Failed to send {feedkey} data (timeout)")
                time.sleep(5)
                continue
              except errors.ThrottlingError:
                logger.error("  Got throttled sending {feedkey} data; wait 30 seconds")
                time.sleep(30)
                continue
          else:
            logger.debug(f"Dropping data [delta: {delta}]: {data} (Queue-{i} size: {q.qsize()})")
        else:
          logger.debug(f"Queue-{i} is empty")
      time.sleep(1)
        
if __name__ == "__main__":

  import threading
  import random

  logger.basicConfig(level=logging.DEBUG)

  io = IOAdafruit('myusername', 'aio_mysecretkeyforaioaccess')

  q = SimpleQueue()
  io.add_q(q)

  thread = threading.Thread(target=io.control_thread, daemon=True)
  thread.start()

  while True:
    d = random.uniform(-10, 110)
    q.put({'timestamp': datetime.now(timezone.utc).timestamp(),
           'name': 'test',
           'vala': d,
           'valb': d/2})
    time.sleep(5)
