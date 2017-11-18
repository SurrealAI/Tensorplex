import redis
from test.common import *


redis.StrictRedis().flushall()
myobj = MyObject(20, 30)

RemoteCall(
    myobj,
    host='localhost',
    port=6379,
    queue_name='remotecall',
    has_client_id=True,
    has_return_value=True
).run()


