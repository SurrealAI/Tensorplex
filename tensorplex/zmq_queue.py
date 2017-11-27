import zmq
import queue
import threading
import time


class ZmqQueueServer(object):
    """
    http://learning-0mq-with-pyzmq.readthedocs.io/en/latest/pyzmq/patterns/pushpull.html
    """
    def __init__(self,
                 port,
                 is_batched,
                 maxsize=0,
                 use_pickle=True,
                 start_thread=True):
        """
        Args:
            max_zmq_buffer: RCVHWM, i.e. "receive high water mark" for ZMQ,
            limits interal buffered size
            https://stackoverflow.com/questions/9385249/limiting-queue-length-with-pyzmq
            http://api.zeromq.org/2-1:zmq-setsockopt

        Warnings:
            HWM doesn't behave as we intuitively expect.
        """
        self._queue = queue.Queue(maxsize=maxsize)
        context = zmq.Context()
        self.socket = context.socket(zmq.PULL)
        # TODO use router-dealer pattern to stall the sender when recv is full
        # https://github.com/zeromq/pyzmq/issues/1111
        self.socket.set_hwm(100)
        self.socket.bind("tcp://127.0.0.1:{}".format(port))
        self._use_pickle = use_pickle
        self._is_batched = is_batched

        self.enqueue_thread = None
        if start_thread:
            self.start_enqueue_thread()

    def start_enqueue_thread(self):
        if self.enqueue_thread is not None:
            raise RuntimeError('enqueue_thread already started')
        self.enqueue_thread = threading.Thread(target=self._run_enqueue)
        self.enqueue_thread.start()
        return self.enqueue_thread

    def _run_enqueue(self):
        while True:
            if self._use_pickle:
                obj = self.socket.recv_pyobj()
            else:
                obj = self.socket.recv()
            if self._is_batched:
                assert isinstance(obj, list)
                for ob in obj:
                    self._queue.put(ob)
            else:
                self._queue.put(obj)

    def dequeue(self, timeout=None):
        return self._queue.get(block=True, timeout=timeout)


class ZmqQueueClient(object):
    def __init__(self,
                 host,
                 port,
                 batch_interval,
                 use_pickle=True,
                 start_thread=True):
        context = zmq.Context()
        self.socket = context.socket(zmq.PUSH)
        self.socket.set_hwm(100)
        self.socket.connect("tcp://{}:{}".format(host, port))
        self._use_pickle = use_pickle
        self._batch_interval = batch_interval
        if self._use_pickle:
            self._send = self.socket.send_pyobj
        else:
            self._send = self.socket.send
        self._batch_buffer = []
        self._batch_lock = threading.Lock()

        self.batch_thread = None
        if self._batch_interval > 0 and start_thread:
            self.start_batch_thread()

    def start_batch_thread(self):
        if self.batch_thread is not None:
            raise ValueError('batch_thread already running')
        self.batch_thread = threading.Thread(target=self._run_batch)
        self.batch_thread.start()
        return self.batch_thread

    def _run_batch(self):
        while True:
            if self._batch_buffer:
                with self._batch_lock:
                    self._send(self._batch_buffer)
                    self._batch_buffer.clear()
            time.sleep(self._batch_interval)

    def enqueue(self, obj):
        if self._batch_interval == 0:  # no batching
            self._send(obj)
        else:
            with self._batch_lock:
                self._batch_buffer.append(obj)

