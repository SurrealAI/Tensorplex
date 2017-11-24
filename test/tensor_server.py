from redis import StrictRedis
from tensorplex import *

os.system('rm -rf ~/Temp/loggerplex/*')
tplex = TensorplexServer('~/Temp/loggerplex',
                         normal_groups=['learner'],
                         combined_groups=['eval'],
                         combined_bin_dict={
                             'eval': [
                                 ('stocha', lambda tag: tag.startswith('stocha')),
                                 ('allothers', lambda tag: True)
                             ]
                         },
                         indexed_groups=['agent', 'individ'],
                         index_bin_sizes=[8, 1])
StrictRedis().flushall()
tplex.start_server('localhost', 6379)
