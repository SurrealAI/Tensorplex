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
    def __init__(self, folder):
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
        self.normal_groups = []
        self.indexed_groups = []
        self._indexed_bin_size = {}
        self.combined_groups = []
        self._combined_tag_to_bin_name = {}

        self._writers = {}  # subfolder_path: SummaryWriter instance
        # following are used in the meta-class method delegation
        self._current_tag = None
        self._current_writer = None

    def register_normal_group(self, name):
        self.normal_groups.append(name)
        subfolder = os.path.join(self.folder, name)
        mkdir(subfolder)
        self._writers[name] = SummaryWriter(subfolder)
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
        assert len(_parts) == 2, 'client str must be "<group>/<id>"'
        group, ID = _parts
        if group in self.normal_groups:
            # normal group root tag is simply ID
            self._current_tag = ID
            self._current_writer = self._writers[group]
        elif group in self.combined_groups:
            # combined group's tag is tuple ("group", "pre-defined bin name")
            self._current_tag = (
                group,
                self._combined_bin_name(group, ID)
            )
            self._current_writer = self._get_sub_writer(group, ID)
        elif group in self.indexed_groups:
            assert str.isdigit(ID), 'indexed group ID must be int'
            ID = int(ID)
            # indexed group's current tag is a tuple ("agent", "8-15")
            self._current_tag = (
                group,
                self._index_bin_name(group, ID)
            )
            self._current_writer = self._get_sub_writer(group, ID)
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
