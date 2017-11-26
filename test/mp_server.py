"""
https://docs.python.org/3/library/multiprocessing.html#using-a-remote-manager
"""

import multiprocessing
from multiprocessing.managers import BaseManager
import queue
queue = queue.Queue()
d = dict()

class QueueManager(BaseManager): pass

QueueManager.register('get_queue', callable=lambda:queue)
QueueManager.register('get_dict', callable=lambda: d)


m = QueueManager(address=('', 8700), authkey=b'abracadabra')
s = m.get_server()
s.serve_forever()