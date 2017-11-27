import json
import os
import inspect
from tensorplex.utils import mkdir
from tensorboardX import SummaryWriter
from collections import namedtuple
import queue
import multiprocessing as mp
import threading
import Pyro4


_DELEGATED_METHODS = [
    'add_scalar',
    'add_audio',
    'add_embedding',
    'add_histogram',
    'add_image',
    'add_text'
]


class _TensorplexWorker(object):
    def __init__(self, root_folder, sub_folder):
        # print('Launch new process', root_folder, sub_folder)
        self.folder = os.path.expanduser(os.path.join(root_folder, sub_folder))
        mkdir(self.folder)
        assert os.path.exists(self.folder), 'cannot create folder '+self.folder
        self.writer = SummaryWriter(self.folder)

    def _delegate(self, tag, *args, _client_tag_, _method_name_, **kwargs):
        "delegate to tensorboard-pytorch methods"
        tag = tag.replace(':', '.').replace('#', '.')
        if isinstance(_client_tag_, tuple):  # indexed group
            group, bin_name = _client_tag_
            if tag.startswith('.') or tag.startswith('/'):
                tag = group + tag + '/' + bin_name
            else:
                tag = group + '/' + tag + '/' + bin_name
        else:  # normal group
            group = _client_tag_
            if tag.startswith('.') or tag.startswith('/'):
                tag = group + tag
            else:
                tag = group + '/' + tag
        getattr(self.writer, _method_name_)(tag, *args, **kwargs)

    def export_json(self, json_path):
        self.writer.export_scalars_to_json(json_path)

    def process(self, queue):
        method_name, client_tag, args, kwargs = queue.get()
        # print('queue:', method_name, args, kwargs, '--', self.folder[-10:])
        if method_name == 'export_json':
            self.export_json(*args, **kwargs)
        else:
            self._delegate(
                *args,
                _method_name_=method_name,
                _client_tag_=client_tag,
                **kwargs
            )


def _run_worker_process(root_folder, sub_folder, queue):
    worker = _TensorplexWorker(root_folder, sub_folder)
    while True:
        worker.process(queue)


class _DelegateMethod(type):
    """
    All methods called on LoggerplexServer will be delegated to self._log
    """
    def __new__(cls, name, bases, attrs):
        for mname in _DELEGATED_METHODS:

            def _method(self,
                        *args,
                        _method_name_=mname,
                        _client_id_,  # required arg
                        **kwargs):
                client_tag, queue = self._get_client_tag(_client_id_)
                queue.put((_method_name_, client_tag, args, kwargs))

            _method.__name__ = mname
            _method = Pyro4.expose(Pyro4.oneway(_method))
            # _method.__doc__ = inspect.getdoc(getattr(SummaryWriter, mname))
            attrs[mname] = _method
        return super().__new__(cls, name, bases, attrs)


class Tensorplex(metaclass=_DelegateMethod):
    EXCLUDE_METHODS = [
        'start_server',
        'register_normal_group',
        'register_combined_group',
        'register_indexed_group',
    ]
    """
    https://github.com/tensorflow/tensorboard/issues/300
    Different folders with same run tag ("agent/1/reward")
        -> different curves (diff color) in the same graph
    Different run tags in the same folder -> same color in different graphs

    Methods:
        add_scalar,
        add_scalars,
        add_audio,
        add_embedding,
        add_histogram,
        add_image,
        add_text

    The first arg to all above methods is `tag`.
    Tag can have '/' or ':' or '.' in it.
    If starts with ':' or '.', the tag will be treated as a separate section.
    '/' groups the rest of the string below a section.
    For example, ':learning:rate/my/group/eps' is under
        "<client_id>.learning.rate" section.
    """
    def __init__(self, folder, parallel_mode='process'):
        """
        Args:
            folder: tensorboard file root folder
            parallel_mode: 'process' or 'thread'
        """
        self.folder = os.path.expanduser(folder)
        mkdir(self.folder)
        assert os.path.exists(self.folder), 'cannot create folder '+self.folder
        self.normal_groups = []
        self.indexed_groups = []
        self._indexed_bin_size = {}
        self.combined_groups = []
        self._combined_tag_to_bin_name = {}
        self._writer_queues = {}  # writer ID: multiprocess.Queue
        assert parallel_mode in ['process', 'thread']
        self._is_process = parallel_mode == 'process'
        # to be used in the delegated methods, call `_set_client_id()` first
        # self._current_client_id = None

    def _add_writer_process(self, sub_folder):
        if sub_folder in self._writer_queues:  # already exists
            return self._writer_queues[sub_folder]
        q = mp.Queue() if self._is_process else queue.Queue()
        Parallelizer = mp.Process if self._is_process else threading.Thread
        proc = Parallelizer(
            target=_run_worker_process,
            args=(self.folder, sub_folder, q)
        )
        proc.daemon = True  # terminate once parent terminates
        proc.start()
        self._writer_queues[sub_folder] = q
        return q

    def register_normal_group(self, name):
        self.normal_groups.append(name)
        self._add_writer_process(name)
        return self

    def register_combined_group(self, name, tag_to_bin_name):
        """
        Args:
            name: group name, will create a subfolder for the group
            tag_to_bin_name: a function that map a tag name to a combined bin
                name. Example: you have 9 different tags
                (red, green, blue, orange, apple, A, B, C, D)
                def tag_to_bin_name(tag):
                    if tag in ['red', 'green', 'blue']:
                        return ':color'  # make a new bin section
                    elif len(tag) == 1:
                        return 'alphabet'
                    else:
                        return ':fruit'
                Your graph will then have 3 curves under "mygroup.color"
                2 curves under "mygroup.fruit", and 4 under "mygroup/alphabet"
        """
        assert callable(tag_to_bin_name)
        self.combined_groups.append(name)
        self._combined_tag_to_bin_name[name] = tag_to_bin_name
        return self

    def register_indexed_group(self, name, bin_size):
        """
        Args:
            name: group name, will create a subfolder for the group
            bin_size: int
                Example: you have 42 processes in the indexed group.
                if bin_size == 10, process 6 will be assigned to the first bin
                "0-9", process 22 will be assigned to the third bin "20-29",
                process 42 will be assigned to the last bin "40-49"
                You don't need to know the total number of processes in advance.
        """
        assert isinstance(bin_size, int) and bin_size > 0
        self.indexed_groups.append(name)
        self._indexed_bin_size[name] = bin_size
        return self

    def _index_bin_name(self, group, ID):
        bin_size = self._indexed_bin_size[group]
        start = ID // bin_size * bin_size
        end = (ID // bin_size + 1) * bin_size - 1
        # end = min(end, N - 1)
        if start == end:
            return str(start)
        else:
            return '{}-{}'.format(start, end)

    def _combined_bin_name(self, group, ID):
        try:
            bin_name = self._combined_tag_to_bin_name[group](ID)
        except Exception as e:
            raise ValueError('tag_to_bin_name function raises exception. '
                     'Its semantics should be (str) -> str that maps a tag '
                     'name to a combined bin name.') from e
        assert isinstance(bin_name, str), \
            'returned bin_name {} must be a string'.format(bin_name)
        return bin_name

    def _get_client_tag(self, client_id):
        """
        Client ID needs to be in the form of "<group>/<id>"
        For NumberedGroup, <id> must be an int, the group will be placed into bins
        according to `bin_size`. For example, if bin_size=8, `agent/0` to
        `agent/7` will be placed in the same graph, `agent/8` to `agent/15 in
        the next graph, etc.
        Each ID in the NumberedGroup will be assigned a separate subfolder
        e.g. <root>/agent/16/, <root>/agent/42/

        Returns:
            (client_tag to be passed to TensorplexWorker, corresponding queue)
        """
        assert '/' in client_id
        _parts = client_id.split('/')
        assert len(_parts) == 2, 'client str must be "<group>/<id>"'
        group, ID = _parts
        if group in self.normal_groups:
            # normal group root tag is simply ID
            return (
                ID,
                self._writer_queues[group]
            )
        elif group in self.combined_groups:
            # combined group's tag is tuple ("group", "pre-defined bin name")
            queue = self._add_writer_process('{}/{}'.format(group, ID))
            return (
                (group, self._combined_bin_name(group, ID)),
                queue
            )
        elif group in self.indexed_groups:
            assert str.isdigit(ID), 'indexed group ID must be int'
            ID = int(ID)
            queue = self._add_writer_process('{}/{}'.format(group, ID))
            # indexed group's current tag is a tuple ("agent", "8-15")
            return (
                (group, self._index_bin_name(group, ID)),
                queue
            )
        else:
            all_groups = (
                self.normal_groups
                + self.combined_groups
                + self.indexed_groups
            )
            if not all_groups:
                raise RuntimeError('You must register at least one group.')
            else:
                raise ValueError('Group "{}" not found. Available groups: {}'
                                 .format(group, all_groups))

    @Pyro4.oneway
    @Pyro4.expose
    def add_scalars(self, tag_scalar_dict, global_step, *, _client_id_):
        """
        Tensorplex's add_scalars() is simply calling add_scalar() multiple times.
        It is NOT the same as `add_scalars()` in the original Tensorboard-pytorch
        API!! The original behavior is more like Tensorplex's "numbered group"
        concept:
        http://tensorboard-pytorch.readthedocs.io/en/latest/_modules/tensorboardX/writer.html#SummaryWriter.add_scalars
        """
        for tag, value in tag_scalar_dict.items():
            self.add_scalar(tag, value,
                            global_step=global_step, _client_id_=_client_id_)

    @Pyro4.oneway
    @Pyro4.expose
    def export_json(self, json_dir):
        """
        Format: {writer_id : [[timestamp, step, value], ...] ...}
        Save to <root>/<json_dir>
        """
        json_dir = os.path.expanduser(os.path.join(self.folder, json_dir))
        mkdir(json_dir)
        for writerID, queue in self._writer_queues.items():
            writerID = writerID.replace('/', '.')
            json_path = os.path.join(json_dir, writerID+'.json')
            queue.put(('export_json', None, (json_path,), {}))
