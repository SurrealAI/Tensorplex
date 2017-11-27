import zmq
from tensorplex.zmq_queue import *


q = ZmqQueueServer(port=8038, is_batched=0, maxsize=2,
                   max_zmq_buffer=10)

for i in range(100):
    if i == 1:
        while True:
            print(list(q._queue.queue))
            time.sleep(1)
    print(q.dequeue())


# context = zmq.Context()
# zmq_socket = context.socket(zmq.PUSH)
# zmq_socket.connect("tcp://127.0.0.1:5557")
# for num in range(20):
#     work_message = { 'num' : num }
#     zmq_socket.send_json(work_message)


