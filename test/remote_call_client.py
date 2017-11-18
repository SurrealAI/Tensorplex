from test.common import *
import time


MyObjectClient = RemoteCall.make_client_class(MyObject, has_return_value=True)

myobj = MyObjectClient(
    client_id='agent1',
    host='localhost',
    port=6379,
    queue_name='remotecall'
)

myobj.tell('msg1', 'msg2', 'msg3')
future1=myobj.mult(factor=1/3)
myobj.tell()
future2=myobj.add(var='y', delta=-50)
myobj.tell()

myobj2 = MyObjectClient(
    client_id='agent2',
    host='localhost',
    port=6379,
    queue_name='remotecall'
)
future3 = myobj2.add(var='x', delta=300)
myobj2.tell('this', 'is', 'agent', 2)

print(future1.get(timeout=1))
# future2.discard()
print(future2.get(timeout=1))
print(future3.get(timeout=6))
