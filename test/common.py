import time
from tensorplex.remote_call import *


class MyObject(object):
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self._client_id = None

    def add(self, delta, var='x'):
        if var == 'x':
            self.x += delta
        else:
            self.y += delta
        time.sleep(3)
        return self._get()

    def mult(self, *, factor):
        self.x *= factor
        self.y *= factor
        return self._get()

    def tell(self, *msg):
        print(msg, self.x, self.y)
        return self._get()

    def _get(self):
        value = '{}({}&{})'.format(self.x, self.y, self._client_id)
        print('INTERNAL', value)
        return value

    def _set_client_id(self, client_id):
        self._client_id = client_id
