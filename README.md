# Tensorplex: distributed Tensorboard and distributed logging

Tensorplex is a multiplexed extension of the popular Tensorboard visualization tool. When you have a cluster, you can collect the learning curves from multiple running nodes and display them side-by-side on a single tensorboard web page. 

Tensorplex makes extensive use of ZeroMQ under the hood, an efficient, robust, and lightweight distributed communication protocol. 

`Loggerplex` is a subcomponent of Tensorplex that does lightweight distributed logging. It collects the real-time logs from multiple nodes and send them to a single master node for persistent book-keeping. 

Tensorplex is not tied to Tensorflow and can be used with any machine learning frameworks that support numpy. 

## Installation

```bash
git clone https://github.com/StanfordVL/Tensorplex.git
pip install -e Tensorplex/
```

## Demo

Go to `Tensorplex/examples/`. Change the tensorboard log folder in `run_server.py` script.

In one command line window, run `python run_server.py`. Then in another window, run `python run_client.py`. The server script should print out a list of `dones`.

Use `tensorboard --logdir ~/Temp/tensorplex/ --port 8009` to view the results.

## Manual

Tensorplex requires one long-running server script. Client scripts can connect and disconnect (e.g. client crashes) without impacting the server.


### Tensorplex server

There are 3 steps to create the server script.

First, initialize a `Tensorplex` object with the root logging folder. Different clients will write to different sub-folders that are created automatically. `max_processes` is the number of processes that the server uses internally. Set it to 4 should be a sweet spot.

```python

tplex = Tensorplex(
    '~/my/logging/folder',
    max_processes=4,
)
```

Second, register the client groups, which helps group Tensorflow curves into the same or different graph windows. The "client IDs" (explained later) in your client scripts must be consistent with the groups you register in the server.

There are 3 types of client groups:

1. `register_normal_group(name)`: each graph will have only one curve in a normal group.
2. `register_indexed_group(name, bin_size)`: each graph will have at most `bin_size` number of curves. Suppose you launch 42 agents with `bin_size=10`, the curves of agent 0-9 will be displayed in the same graph window; likewise, the curves of 10-19, 20-29, 30-39, 40-41 will be grouped in their respective graphs.
3. `register_combined_group(name, group_criterion)`: TODO


To register multiple groups, you can chain the commands:

```python
(tplex
    .register_normal_group('learner')  # 1 curve per graph
    .register_indexed_group('agent', 8)  # 8 agent learning curves per graph
    .register_indexed_group('eval', 4)  # 4 eval curves per graph
    .register_combined_group('eval', get_eval_bin_name)
 )
```

Third, you specify a port and launch the server. The script will be blocking:

```python
tplex.start_server(8008)
# block main thread forever
```

### Tensorplex client

Every `TensorplexClient` object must have a client ID that looks like `<group_name>/<client_name>`, i.e. two string names separated by `/`.

```python
client = TensorplexClient(
    client_id='agent/0',  # for indexed group
    # client_id='learner/system_stats',  # for normal group, here client_name is `system_stats`
    host='123.45.6.7',  # server address to connect
    port=8008,  # server port to connect
)
```

Then you can write statistics to TensorplexClient

```python
# most fundamental method
client.add_scalar(tag, 3.1415, integer_step)
# add_scalars is equivalent to multiple add_scalar() in one line
client.add_scalars({tag: 3.1415, tag2: 2.71828, tag3: 42}, integer_step)
```

There are

Note that `tag` in `add_scalar` behaves differently for different client group types.

For normal group,
