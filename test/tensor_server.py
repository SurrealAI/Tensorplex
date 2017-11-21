from redis import StrictRedis
from tensorplex import *

NG = NumberedGroup

tplex = TensorplexServer('~/Temp/loggerplex',
                         normal_groups=['learner', 'eval'],
                         numbered_groups=[NG('agent', 27, 8),
                                    NG('duplic', 13, 6),
                                    NG('individ', 5, 1)])
StrictRedis().flushall()
tplex.start_server('localhost', 6379)
