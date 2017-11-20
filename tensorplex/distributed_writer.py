import redis
import numpy as np
import json
from tensorboardX import SummaryWriter
from .remote_call import RemoteCall

class DistributedWriter(object):

    def __init__(self, num_sets):
        self.num_sets = num_sets
        self.writers = []

        log_root = "tensorboard/" 
        for i in range(num_sets):
            self.writers.append(SummaryWriter(log_dir=log_root + "set_{}".format(i)))

    def add_audio(self, setID, tag, snd_tensor, global_step=None, sample_rate=44100):
        self.writers[setID].add_audio(tag, snd_tensor, global_step, sample_rate)

    def add_embedding(self, setID, mat, metadata=None, label_img=None, global_step=None, tag='default'):
        self.writers[setID].add_embedding(mat, metadata, label_img, global_step, tag)

    def add_graph(self, setID, model, lastVar):
        self.writers[setID].add_graph(model, lastVar)

    def add_histogram(self, setID, tag, values, global_step=None, bins='tensorflow'):
        self.writers[setID].add_histogram(tag, values, global_step, bins)

    def add_image(self, setID, tag, img_tensor, global_step=None):
        self.writers[setID].add_image(tag, img_tensor, global_step)

    def add_pr_curve(self, setID, tag, labels, predictions, global_step=None, num_thresholds=127, weights=None):
        self.writers[setID].add_pr_curve(labels, predictions, global_step, num_thresholds, weights)

    def add_scalar(self, setID, tag, scalar_value, global_step=None):
        self.writers[setID].add_scalar(tag, scalar_value, global_step)

    def add_scalars(self, setID, main_tag, tag_scalar_dict, global_step=None):
        self.writers[setID].add_scalars(main_tag, tag_scalar_dict, global_step)

    def add_text(self, setID, tag, text_string, global_step=None):
        self.writers[setID].add_text(tag, text_string, global_step)

    def export_scalars_to_json(self, setID, path):
        self.writers[setID].export_scalars_to_json(path)


def make_writer_client(has_return_value, client_id, host, port=6379, queue_name='remotecall'):
    DistributedWriterClient = RemoteCall.make_client_class(DistributedWriter, has_return_value=has_return_value)
    return DistributedWriterClient(
            client_id= client_id,
            host=host,
            port=port,
            queue_name=queue_name
    )

def make_writer_server(num_sets, host, port=6379, queue_name='remotecall', has_client_id=False, has_return_value=False):
    writer = DistributedWriter(num_sets)
    RemoteCall(
        writer, 
        host=host,
        port=6379,
        queue_name='remotecall',
        has_client_id=False,
        has_return_value=False
    ).run()