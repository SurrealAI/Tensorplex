import multiprocessing as mp
import os
import queue
import threading
from collections import namedtuple

from tensorboardX import SummaryWriter
from .local_proxy import LocalProxy

from .utils import mkdir, delegate_methods


_DELEGATED_METHODS = [
    'add_scalar',
    'add_audio',
    'add_embedding',
    'add_histogram',
    'add_image',
    'add_text'
]


class _Writer(object):
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

    def _export_json(self, json_path):
        self.writer.export_scalars_to_json(json_path)

    def process(self, method_name, client_tag, args, kwargs):
        # print('queue:', method_name, args, kwargs, '--', self.folder[-10:])
        if method_name == 'export_json':
            self._export_json(*args, **kwargs)
        else:
            self._delegate(
                *args,
                _method_name_=method_name,
                _client_tag_=client_tag,
                **kwargs
            )


# notify WriterGroup on a separate process to create a new writer
_AddWriterRequest = namedtuple('_AddWriterRequest',
                               'writerID root_folder sub_folder')

# dummy value to ask WriterGroup to print something
# debugging: useful to check when the queue on the WriterGroup process is "done"
_PrintRequest = namedtuple('_PrintRequest', 'writerID msg')


class _WriterGroup(object):
    """
    Each WriterGroup lives on a separate process
    """
    def __init__(self, proc_id, queue, parallel_cls):
        self._pool = {}  # writerID: _Writer instance
        self._proc_id = proc_id  # process ID, for debugging
        self._queue = queue
        self.ProcessCls = parallel_cls

    def _add_writer(self, writerID, root_folder, sub_folder):
        # print('newwriter', self._proc_id, writerID, root_folder, sub_folder)
        self._pool[writerID] = _Writer(root_folder, sub_folder)

    def _process(self, writerID, writer_args):
        assert writerID in self._pool
        writer = self._pool[writerID]
        writer.process(*writer_args)

    def _dequeue_loop(self):
        while True:
            msg = self._queue.get()
            if isinstance(msg, _AddWriterRequest):
                self._add_writer(*msg)
            elif isinstance(msg, _PrintRequest):
                print(*msg)  # debugging, check done
            else:  # normal writer workload request
                self._process(*msg)

    def run(self):
        "after run(), everything should be communicated through queue"
        proc = self.ProcessCls(target=self._dequeue_loop)
        proc.daemon = True
        proc.start()


class _ProcessPool(object):
    def __init__(self, root_folder, max_processes):
        self._root_folder = root_folder
        self._occupancy = []  # writer count per process, for load balancing
        self._proc_queues = []
        if max_processes == 0:
            self._is_thread = True
            max_processes = 1
        else:
            self._is_thread = False
        self._max_procs = max_processes
        self._writer_id_queue = {}

    def _select_process(self):
        "select the next vacant process, returns queue associated"
        assert len(self._occupancy) == len(self._proc_queues)
        if len(self._proc_queues) < self._max_procs:
            # create a new proc (one _WriterGroup per proc)
            q = mp.Queue()
            self._occupancy.append(1)
            self._proc_queues.append(q)
            _WriterGroup(
                proc_id=len(self._occupancy)-1,
                queue=q,
                parallel_cls=threading.Thread if self._is_thread else mp.Process
            ).run()
            return q
        else:
            # get the smallest occupancy, and return the queue
            idx = self._occupancy.index(min(self._occupancy))
            self._occupancy[idx] += 1
            return self._proc_queues[idx]

    def submit(self, writerID, writer_args):
        if writerID not in self._writer_id_queue:
            queue = self._select_process()
            self._writer_id_queue[writerID] = queue
            # request to add a new writer to _WriterGroup process
            queue.put(_AddWriterRequest(
                writerID=writerID,
                root_folder=self._root_folder,
                sub_folder=writerID  # by convention
            ))
        queue = self._writer_id_queue[writerID]
        # now we are ready to put the real workload
        queue.put((writerID, writer_args))

    def all_writer_ids(self):
        return list(self._writer_id_queue.keys())

    def print_done(self):
        "debugging"
        for writerID in self.all_writer_ids():
            queue = self._writer_id_queue[writerID]
            queue.put(_PrintRequest(writerID, 'done'))


class Tensorplex(object):
    _EXCLUDE_METHODS = [
        'register_normal_group',
        'register_combined_group',
        'register_indexed_group',
        'proxy',
        'start_server',
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
    def __init__(self, root_folder, max_processes):
        """
        Args:
            root_folder: tensorboard file root folder
            max_processes: 0 to use thread instead of process
        """
        self.folder = os.path.expanduser(root_folder)
        mkdir(self.folder)
        assert os.path.exists(self.folder), 'cannot create folder '+self.folder
        self.normal_groups = []
        self.indexed_groups = []
        self._indexed_bin_size = {}
        self.combined_groups = []
        self._combined_tag_to_bin_name = {}

        self._process_pool = _ProcessPool(
            root_folder=root_folder,
            max_processes=max_processes,
        )

    def register_normal_group(self, name):
        self.normal_groups.append(name)
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
            (client_tag to be passed to TensorplexWorker, writerID)
        """
        assert '/' in client_id
        _parts = client_id.split('/')
        assert len(_parts) == 2, 'client str must be "<group>/<id>"'
        group, ID = _parts
        if group in self.normal_groups:
            # normal group root tag is simply ID
            return (
                ID,
                group
            )
        elif group in self.combined_groups:
            # combined group's tag is tuple ("group", "pre-defined bin name")
            return (
                (group, self._combined_bin_name(group, ID)),
                '{}/{}'.format(group, ID)
            )
        elif group in self.indexed_groups:
            assert str.isdigit(ID), 'indexed group ID must be int'
            ID = int(ID)
            # indexed group's current tag is a tuple ("agent", "8-15")
            return (
                (group, self._index_bin_name(group, ID)),
                '{}/{}'.format(group, ID)
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

    def add_scalars(self, tag_scalar_dict, global_step, *, _client_id_):
        """
        Tensorplex's add_scalars() is simply calling add_scalar() multiple times.
        It is NOT the same as `add_scalars()` in the original Tensorboard-pytorch
        API!! The original behavior is more like Tensorplex's "numbered group"
        concept:
        http://tensorboard-pytorch.readthedocs.io/en/latest/_modules/tensorboardX/writer.html#SummaryWriter.add_scalars
        """
        for tag, value in tag_scalar_dict.items():
            self.add_scalar(
                tag,
                value,
                global_step=global_step,
                _client_id_=_client_id_
            )

    def export_json(self, json_dir):
        """
        Format: {writer_id : [[timestamp, step, value], ...] ...}
        Save to <root>/<json_dir>
        """
        json_dir = os.path.expanduser(os.path.join(self.folder, json_dir))
        mkdir(json_dir)
        for writerID in self._process_pool.all_writer_ids():
            json_path = os.path.join(
                json_dir,
                writerID.replace('/', '.')+'.json'
            )
            self._process_pool.submit(
                writerID,
                ('export_json', None, (json_path,), {})
            )

    def proxy(self, client_id):
        return LocalProxy(self, client_id,
                          exclude=self._EXCLUDE_METHODS)

    def print_done(self):
        "debugging only"
        self._process_pool.print_done()


def _wrap_method(method_name, old_method):
    def _method(self, *args, _client_id_, **kwargs):
        client_tag, writerID = self._get_client_tag(_client_id_)
        self._process_pool.submit(
            writerID,
            (method_name, client_tag, args, kwargs)
        )
    return _method


delegate_methods(
    target_obj=Tensorplex,
    src_obj=SummaryWriter,
    wrapper=_wrap_method,
    doc_signature=True,
    include=_DELEGATED_METHODS,
)

