import math
from tensorplex import TensorplexClient

PORT = 8008


def plot(client, shift):
    x = math.pi / 200
    for i in range(0, 300):
        v1 = math.sin(x*i +math.pi*shift) * (1+shift)
        v2 = math.sin(x*i +math.pi*shift) * (1+shift)* math.exp(i/200)
        v3 = 2 * math.cos(x*i + math.pi*shift)/(1+shift) * math.exp(-i/100)
        # prefix the tag name with a period to create a different section
        client.add_scalar('.my.section/foo', v1, i)
        client.add_scalar('.my.section/bar', v2, i)
        client.add_scalar('mystats', v3, i)
        # add_scalars() is equivalent to multiple add_scalar()
        # client.add_scalars({'.my.section/foo': v1, '.my.section/bar': v2, 'mystats': v3}, i)


# normal group
# e.g. client names can be system stats (throughput, latency),
# training stats (loss, Q value, gradient magnitude),
# environment stats (FPS, rewards)
for step, client_name in enumerate(['system', 'training', 'env']):
    client = TensorplexClient(
        client_id='learner/' + client_name,
        host='localhost',
        port=PORT,
    )
    # for illustration purpose, 0.1*step here has no meaning other than rendering the curves distinct
    plot(client, 0.1 * step)

# indexed group
for step in range(27):
    agent_id = step  # for illustration purpose
    client = TensorplexClient(
        client_id='agent/'+str(agent_id),  # client name is a number for indexed group
        host='localhost',
        port=PORT,
    )
    plot(client, -0.12 * step)

for step in range(10):
    eval_id = step
    client = TensorplexClient(
        client_id='eval/'+str(eval_id),
        host='localhost',
        port=PORT,
    )
    plot(client, 0.2 * step)

# combined group
for step, client_name in enumerate(['PPO', 'DDPG', 'DQN', 'ES', 'GA']):
    client = TensorplexClient(
        client_id='ablation/' + client_name,
        host='localhost',
        port=PORT,
    )
    plot(client, 1 * step)

client.print_done()  # debugging
# t.export_json('json')

