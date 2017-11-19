from redis import StrictRedis
from tensorplex import *


logger = Loggerplex('~/Temp/loggerplex', overwrite=1, debug=1)
StrictRedis().flushall()
logger.start_remote_call('localhost', 6379)
