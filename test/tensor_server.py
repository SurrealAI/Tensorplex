from redis import StrictRedis
from tensorplex import *

tplex = TensorplexServer('~/Temp/loggerplex',
                         normal_groups=['learner', 'eval'],
                         indexed_groups=['agent', 'multip', 'individ'],
                         index_bin_sizes=[8, 6, 1])
StrictRedis().flushall()
tplex.start_server('localhost', 6379)
