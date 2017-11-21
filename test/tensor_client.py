from test.common import *
import math
import traceback
import io


def plot(writer, shift):
    x = math.pi / 200
    for i in range(0, 300):
        writer.add_scalar('sin', math.sin(x*i +math.pi*shift) * (1+shift), i)
        writer.add_scalar('cos', 2 * math.cos(x*i + math.pi*shift)/(1+shift) * math.exp(-i/100), i)


for i in range(27):
    t = TensorplexClient(
        client_id='agent/'+str(i),
        host='localhost',
        port=6379,
    )
    plot(t, 0.08 * i)

for i in range(13):
    t = TensorplexClient(
        client_id='duplic/'+str(i),
        host='localhost',
        port=6379,
    )
    plot(t, -0.12 * i)

for i in range(5):
    t = TensorplexClient(
        client_id='individ/'+str(i),
        host='localhost',
        port=6379,
    )
    plot(t, 0.2 * i)

for i, tag in enumerate(['lr', 'momentum', 'eps']):
    t = TensorplexClient(
        client_id='learner/'+tag,
        host='localhost',
        port=6379,
    )
    plot(t, 0.1 * i)

for i, tag in enumerate(['score', 'speed_iter_s']):
    t = TensorplexClient(
        client_id='eval/'+tag,
        host='localhost',
        port=6379,
    )
    plot(t, 1 * i)
