from redis import StrictRedis
from tensorplex import *


logger = Loggerplex('~/Temp/loggerplex', overwrite=1, debug=1)
logger.start_server(6379)
