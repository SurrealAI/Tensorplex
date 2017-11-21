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
                # access two properties: self._current_writer and _current_tag
                tag = tag.replace(':', '.').replace('#', '.')
                if isinstance(self._current_tag, tuple):  # indexed group
                    group, bin_str = self._current_tag
                    if tag.startswith('.') or tag.startswith('/'):
                        tag = group + tag + '/' + bin_str
                    else:
                        tag = group + '/' + tag + '/' + bin_str
                else:  # normal group
                    group = self._current_tag
                    if tag.startswith('.') or tag.startswith('/'):
                        tag = group + tag
                    else:
                        tag = group + '/' + tag
                getattr(self._current_writer, __name)(tag, *args, **kwargs )

            _method.__doc__ = inspect.getdoc(getattr(SummaryWriter, mname))
            attrs[mname] = _method
        return super().__new__(cls, name, bases, attrs)


class TensorplexServer(metaclass=_DelegateMethod):
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
    def __init__(self,
                 folder,
                 normal_groups,
                 indexed_groups,
                 index_bin_sizes):
        """
        Args:
            folder: tensorboard file root folder
            normal_groups: a list of normal group names
            indexed_groups: a list of indexed group names
            index_bin_sizes: list of bin sizes for each numbered group
        """
        self.folder = os.path.expanduser(folder)
        mkdir(self.folder)
        assert os.path.exists(self.folder), 'cannot create folder '+self.folder
        assert isinstance(normal_groups, list)
        self._normal_groups = normal_groups
        assert isinstance(indexed_groups, list)
        assert isinstance(index_bin_sizes, list)
        assert len(index_bin_sizes) == len(indexed_groups)
        self._indexed_groups = dict(zip(indexed_groups, index_bin_sizes))

        self._writers = {}  # subfolder_path: SummaryWriter instance
        for g in self._normal_groups:
            assert isinstance(g, str), 'normal group name {} must be str'.format(g)
            subfolder = os.path.join(self.folder, g)
            mkdir(subfolder)
            self._writers[g] = SummaryWriter(subfolder)
        # following are used in the meta-class method delegation
        self._current_tag = None
        self._current_writer = None

    def _get_index_writer(self, group, index):
        writerID = '{}/{}'.format(group, index)
        if writerID not in self._writers:
            # index doesn't exist yet, create a new writer
            subfolder = os.path.join(self.folder, writerID)
            mkdir(subfolder)
            self._writers[writerID] = SummaryWriter(subfolder)
        return self._writers[writerID]

    def _get_bin_str(self, ID, bin_size):
        start = ID // bin_size * bin_size
        end = (ID // bin_size + 1) * bin_size - 1
        # end = min(end, N - 1)
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
            # normal group root tag will simply be ID
            self._current_tag = ID
            self._current_writer = self._writers[group]
        elif group in self._indexed_groups:
            assert str.isdigit(ID), 'numbered group ID must be int'
            ID = int(ID)
            # indexed group's current tag is a tuple ("agent", "8-15")
            self._current_tag = (
                group,
                self._get_bin_str(ID, self._indexed_groups[group])
            )
            self._current_writer = self._get_index_writer(group, ID)
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
