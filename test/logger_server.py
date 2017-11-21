from redis import StrictRedis
from tensorplex import *


logger = LoggerplexServer('~/Temp/loggerplex', overwrite=1, debug=1)
StrictRedis().flushall()
logger.start_server('localhost', 6379)
