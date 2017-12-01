from redis import StrictRedis
from tensorplex import *


logger = Loggerplex('~/Temp/loggerplex', overwrite=1, level='debug')
logger.start_server(6379)
