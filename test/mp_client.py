"""
https://docs.python.org/3/library/multiprocessing.html#using-a-remote-manager
"""
from multiprocessing.managers import BaseManager

class QueueManager(BaseManager): pass

QueueManager.register('get_queue')
QueueManager.register('get_dict')

m = QueueManager(address=('127.0.0.1', 8700), authkey=b'abracadabra')
m.connect()
queue = m.get_queue()
d = m.get_dict()
# print(queue.get())

# print(d)
