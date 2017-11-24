from test.common import *
import math
import traceback
import io


def plot(writer, shift):
    x = math.pi / 200
    for i in range(0, 300):
        v1 = math.sin(x*i +math.pi*shift) * (1+shift)
        v2 = math.sin(x*i +math.pi*shift) * (1+shift)* math.exp(i/200)
        v3 = 2 * math.cos(x*i + math.pi*shift)/(1+shift) * math.exp(-i/100)
        writer.add_scalar('.my#section/foo', v1, i)
        writer.add_scalar(':my.section/bar', v2, i)
        writer.add_scalar('cos', v3, i)
        writer.add_scalars({'yo': v1, ':yo': v2, ':yo.yo': v3}, i)


for i in range(27):
    t = TensorplexClient(
        client_id='agent/'+str(i),
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

for i, tag in enumerate(['deterministic', 'stochastic-1', 'stochastic-2', 'exploratory']):
    t = TensorplexClient(
        client_id='eval/'+tag,
        host='localhost',
        port=6379,
    )
    plot(t, 1 * i)

t.export_json('~/Temp/loggerplex/scalars.json')