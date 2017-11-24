import json
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
                    group, bin_name = self._current_tag
                    if tag.startswith('.') or tag.startswith('/'):
                        tag = group + tag + '/' + bin_name
                    else:
                        tag = group + '/' + tag + '/' + bin_name
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
                 combined_groups,
                 combined_bin_dict,  # TODO dict of list of (bin_name, criterion)
                 indexed_groups,
                 index_bin_sizes):
        """
        Args:
            folder: tensorboard file root folder
            normal_groups: list of normal group names
            indexed_groups: list of indexed group names
            index_bin_sizes: list of bin sizes for each numbered group
        """
        self.folder = os.path.expanduser(folder)
        mkdir(self.folder)
        assert os.path.exists(self.folder), 'cannot create folder '+self.folder
        assert isinstance(normal_groups, list)
        self._normal_groups = normal_groups
        assert isinstance(combined_groups, list)
        self._combined_groups = combined_groups
        self._combined_bin_dict = combined_bin_dict
        assert isinstance(indexed_groups, list)
        assert isinstance(index_bin_sizes, list)
        assert len(index_bin_sizes) == len(indexed_groups)
        self._index_bin_size = dict(zip(indexed_groups, index_bin_sizes))

        self._writers = {}  # subfolder_path: SummaryWriter instance
        for g in self._normal_groups:
            assert isinstance(g, str), 'normal group name {} must be str'.format(g)
            subfolder = os.path.join(self.folder, g)
            mkdir(subfolder)
            self._writers[g] = SummaryWriter(subfolder)
        # following are used in the meta-class method delegation
        self._current_tag = None
        self._current_writer = None

    def _get_sub_writer(self, group, index):
        """
        Used by both indexed group and combined group
        """
        writerID = '{}/{}'.format(group, index)
        if writerID not in self._writers:
            # index doesn't exist yet, create a new writer
            subfolder = os.path.join(self.folder, writerID)
            mkdir(subfolder)
            self._writers[writerID] = SummaryWriter(subfolder)
        return self._writers[writerID]

    def _index_bin_name(self, group, ID):
        bin_size = self._index_bin_size[group]
        start = ID // bin_size * bin_size
        end = (ID // bin_size + 1) * bin_size - 1
        # end = min(end, N - 1)
        if start == end:
            return str(start)
        else:
            return '{}-{}'.format(start, end)

    def _combined_bin_name(self, group, ID):
        for bin_name, criterion in self._combined_bin_dict[group]:
            if callable(criterion) and criterion(ID):
                return bin_name
            elif isinstance(criterion, list) and ID in criterion:
                return bin_name
        return ID  # no bin found, fallback

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
            # normal group root tag is simply ID
            self._current_tag = ID
            self._current_writer = self._writers[group]
        elif group in self._combined_groups:
            # combined group's tag is tuple ("group", "pre-defined bin name")
            self._current_tag = (
                group,
                self._combined_bin_name(group, ID)
            )
            self._current_writer = self._get_sub_writer(group, ID)
        elif group in self._index_bin_size:
            assert str.isdigit(ID), 'numbered group ID must be int'
            ID = int(ID)
            # indexed group's current tag is a tuple ("agent", "8-15")
            self._current_tag = (
                group,
                self._index_bin_name(group, ID)
            )
            self._current_writer = self._get_sub_writer(group, ID)
        else:
            raise ValueError('Group "{}" not found'.format(group))

    def add_scalars(self, tag_scalar_dict, global_step):
        """
        Tensorplex's add_scalars() is simply calling add_scalar() multiple times.
        It is NOT the same as `add_scalars()` in the original Tensorboard-pytorch
        API!! The original behavior is more like Tensorplex's "numbered group"
        concept:
        http://tensorboard-pytorch.readthedocs.io/en/latest/_modules/tensorboardX/writer.html#SummaryWriter.add_scalars
        """
        for tag, value in tag_scalar_dict.items():
            self.add_scalar(tag, value, global_step=global_step)

    def export_scalar_dict(self):
        """
        Format: {writer_id : [[timestamp, step, value], ...] ...}

        http://tensorboard-pytorch.readthedocs.io/en/latest/_modules/tensorboardX/writer.html#SummaryWriter.export_scalars_to_json
        """
        return {writerID: writer.scalar_dict
                for writerID, writer
                in self._writers.items()}

    def export_json(self, file_path, indent=4):
        """
        Format: {writer_id : [[timestamp, step, value], ...] ...}
        """
        file_path = os.path.expanduser(file_path)
        with open(file_path, 'w') as f:
            json.dump(self.export_scalar_dict(), f, indent=indent)

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
    exclude_methods=[
        'start_server',
        'register_normal_group',
        'register_combined_group',
        'register_indexed_group',
    ],
)
