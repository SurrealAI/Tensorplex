from redis import StrictRedis
from test.common import *
from tensorplex.experimental import *

os.system('rm -rf ~/Temp/loggerplex/*')


tplex = Tensorplex('~/Temp/loggerplex')

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

# StrictRedis().flushall()
# tplex.start_server('localhost', 6379)

start_tensorplex_server(tplex, 8008)
