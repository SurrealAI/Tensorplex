from redis import StrictRedis
from test.common import *

os.system('rm -rf ~/Temp/loggerplex/*')


tplex = Tensorplex(
    '~/Temp/loggerplex',
    max_processes=4,
)

def get_eval_bin_name(tag):
    if tag.startswith('stocha'):
        return 'stocha'
    else:
        return 'others'

(tplex
    .register_normal_group('learner')
    .register_combined_group('eval', get_eval_bin_name)
    .register_indexed_group('agent', 8)
    .register_indexed_group('individ', 1)
 )

def timerrun():
    print('begin counting')
    i = 0
    while True:
        time.sleep(1)
        i += 1
        print(i, 's')

threading.Thread(target=timerrun).start()
# start_tensorplex_server(tplex, 8007, 8008)  # for Pyro
tplex.start_server(8008)  # for Zmq
