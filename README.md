# Tensorplex: distributed Tensorboard and logging

Tensorboard and text logging for multiple processes.


## Remote Call API

Remote call API uses Redis to execute a call on an object remotely. The API has two components: client side and server side. 

Let's take the following dummy class as an example. The API works with any blackbox class. If you set `has_client_id=True` option in RemoteCall, your class needs to implement the `_set_client_id(self, client_id)` method. Depending on the `client_id`, the class methods might have different behaviors. For example, `client_id` will indicate which log file to write to in a distributed setting. 

```python
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
        return self.x + self.y + self._client_id

    def mult(self, factor):
        self.x *= factor
        self.y *= factor
        return self.x * self.y * self._client_id
    
    def _set_client_id(self, client_id):
        # this method is only required if you set `has_client_id=True`
        self._client_id = client_id
```

### Server side

The object is instantiated only on the server. The client will never create the object, or even touch `MyObject` class. That means client will never call `__init__()` on `MyObject`. 

Server side sample code:

```python
myobj = MyObject(x=20, y=42)

RemoteCall(
    myobj,
    host='192.168.0.0',  # redis address
    port=6379,
    queue_name='remotecall',  # must be the same as client
    has_client_id=True,
    has_return_value=True
).run()
```

`run()` method starts the request-handling loop (producer-consumer pattern).


### Client side

Client side will only call the class methods through a proxy class, created by the static method `RemoteCall.make_client_class`. The proxy class has exactly the same interface (same method signatures) as the original class.

The proxy methods will return a `RemoteFuture` object only if `has_return_value=True` on both server and client sides. `RemoteFuture` has two methods:

* `get(timeout=0)`: return None if timed out. Wait indefinitely for the result when timeout=0.
* `discard()`: discard the future and cleans up the references in Redis.

```python
MyObjectClient = RemoteCall.make_client_class(MyObject, has_return_value=True)

myobj = MyObjectClient(
    client_id='agent1',
    host='192.168.0.0',
    port=6379,
    queue_name='remotecall'  # must match the server queue name
)

# returns a future object only if `has_return_value=True`
future1 = myobj.add(10, var='y')
future2 = myobj.mult(-2)

print(future1.get(timeout=1))  # None if timeout
print(future2.get())  # wait indefinitely until the result comes
```

