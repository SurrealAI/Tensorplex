import zmq
from tensorplex.zmq_queue import *


q = ZmqQueueClient(host='127.0.0.1',
                   port=8038,
                   flush_time=0,
                   max_zmq_buffer=3)

for i in range(100):
    q.enqueue('obj'+str(i))
    time.sleep(0.2)


# context = zmq.Context()
# results_receiver = context.socket(zmq.PULL)
# results_receiver.bind("tcp://127.0.0.1:5557")
# while True:
#     result = results_receiver.recv_json()
#     print(result)

