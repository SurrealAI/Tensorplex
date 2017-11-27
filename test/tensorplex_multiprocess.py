"""
Run Tensorplex completely locally, without Redis.
Can be used with multiprocess/multithreading
"""
import math
import threading
import multiprocessing
from test.common import *
from tensorplex.experimental import Tensorplex
from tensorboardX import SummaryWriter


def clear():
    os.system('rm -rf ~/Temp/loggerplex/*')

clear()
mode = 'thread'
mode = 'process'

if 1:
    t = Tensorplex('~/Temp/loggerplex', parallel_mode=mode)

    def get_eval_bin_name(tag):
        if tag.startswith('stocha'):
            return 'stocha'
        else:
            return 'others'

    (t
     .register_normal_group('learner')
     .register_combined_group('eval', get_eval_bin_name)
     .register_indexed_group('agent', 8)
     .register_indexed_group('individ', 1)
     )
else:
    t = SummaryWriter(os.path.expanduser('~/Temp/loggerplex'))
    t.set_client_id = lambda *args, **kwargs: 0


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


def run0():
    for i in range(27):
        t.set_client_id(
            client_id='agent/'+str(i),
        )
        plot(t, -0.12 * i)

def run1():
    for i in range(5):
        t.set_client_id(
            client_id='individ/'+str(i),
        )
        plot(t, 0.2 * i)

def run2():
    for i, tag in enumerate(['lr', 'momentum', 'eps']):
        t.set_client_id(
            client_id='learner/'+tag,
        )
        plot(t, 0.1 * i)

def run3():
    for i, tag in enumerate(['deterministic', 'stochastic-1', 'stochastic-2', 'exploratory']):
        t.set_client_id(
            client_id='eval/'+tag,
        )
        plot(t, 1 * i)

with Timer():
    run0()
    run1()
    run2()
    run3()

print('DONE')
time.sleep(5)
t.export_json('mydir')
time.sleep(100)

# tplex.export_json('~/Temp/loggerplex/scalars.json')
