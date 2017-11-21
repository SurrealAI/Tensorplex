import logging
import os
import inspect
from .remote_call import RemoteCall, mkdir
from tensorboardX import SummaryWriter
from collections import namedtuple


class _DelegateMethod(type):
    """
    All methods called on LoggerplexServer will be delegated to self._log
    """
    def __new__(cls, name, bases, attrs):
        method_names = [
            'add_scalar',
            'add_scalars',
            'add_audio',
            'add_embedding',
            'add_histogram',
            'add_image',
            'add_text'
        ]
        for mname in method_names:
            def _method(self, tag, *args, __name=mname, **kwargs):
                getattr(self._current_writer, __name)(
                    self._current_tag+'/'+tag,
                    *args, **kwargs
                )
            _method.__doc__ = inspect.getdoc(getattr(SummaryWriter, mname))
            attrs[mname] = _method
        return super().__new__(cls, name, bases, attrs)


NumberedGroup = namedtuple('NumberedGroup', 'name, N, bin_size')


class TensorplexServer(metaclass=_DelegateMethod):
    """
    https://github.com/tensorflow/tensorboard/issues/300
    Different folders with same run tag ("agent/1/reward")
        -> different curves (diff color) in the same graph
    Different run tags in the same folder -> same color in different graphs
    """
    def __init__(self,
                 folder,
                 normal_groups,
                 numbered_groups):
        """
        Args:
            folder: tensorboard file root folder
            normal_groups: a list of group names
            numbered_groups: a list of NumberedGroup tuples
        """
        self.folder = os.path.expanduser(folder)
        mkdir(self.folder)
        assert os.path.exists(self.folder), 'cannot create folder '+self.folder
        assert isinstance(normal_groups, list)
        self._normal_groups = normal_groups
        assert isinstance(numbered_groups, list)
        self._numbered_groups = {}
        for g in numbered_groups:
            assert isinstance(g, NumberedGroup)
            self._numbered_groups[g.name] = g

        self._writers = {}  # subfolder_path: SummaryWriter instance
        for g in self._normal_groups:
            assert isinstance(g, str), 'normal group name {} must be str'.format(g)
            subfolder = os.path.join(self.folder, g)
            mkdir(subfolder)
            self._writers[g] = SummaryWriter(subfolder)
        for g in self._numbered_groups.values():
            name, N, bin_size = g
            assert N > 1 and bin_size > 0
            for i in range(N):
                writerID = '{}/{}'.format(name, i)
                subfolder = os.path.join(self.folder, writerID)
                mkdir(subfolder)
                self._writers[writerID] = SummaryWriter(subfolder)
        self._current_tag = None
        self._current_writer = None

    def _get_bin_str(self, ID, N, bin_size):
        assert 0 <= ID < N
        start = ID // bin_size * bin_size
        end = (ID // bin_size + 1) * bin_size - 1
        end = min(end, N - 1)
        if start == end:
            return str(start)
        else:
            return '{}-{}'.format(start, end)

    def _set_client_id(self, client_id):
        """
        Client ID needs to be in the form of "<group>/<id>"
        For NumberedGroup, <id> must be an int, the group will be placed into bins
        according to `bin_size`. For example, if bin_size=8, `agent/0` to
        `agent/7` will be placed in the same graph, `agent/8` to `agent/15 in
        the next graph, etc.
        Each ID in the NumberedGroup will be assigned a separate subfolder
        e.g. <root>/agent/16/, <root>/agent/42/
        """
        assert '/' in client_id
        _parts = client_id.split('/')
        assert len(_parts) == 2
        group, ID = _parts
        if group in self._normal_groups:
            # ID will be the root tag
            self._current_tag = ID
            self._current_writer = self._writers[group]
        elif group in self._numbered_groups:
            assert str.isdigit(ID), 'numbered group ID must be int'
            ID = int(ID)
            group_spec = self._numbered_groups[group]
            N, bin_size = group_spec.N, group_spec.bin_size
            assert 0 <= ID < N, \
                '{} ID {} must be in range [0, {})'.format(group, ID, N)
            # current tag looks like 0-7 or 8-15
            self._current_tag = '{}/{}'.format(
                group,
                self._get_bin_str(ID, N, bin_size)
            )
            self._current_writer = self._writers[client_id]
        else:
            raise ValueError('Group "{}" not found'.format(group))

    def start_server(self, host, port):
        RemoteCall(
            self,
            host=host,
            port=port,
            queue_name=self.__class__.__name__,
            has_client_id=True,
            has_return_value=False
        ).run()


TensorplexClient = RemoteCall.make_client_class(
    TensorplexServer,
    new_cls_name='TensorplexClient',
    has_return_value=False,
)
