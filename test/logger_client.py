from test.common import *
import traceback
import io

client = 0

logger = LoggerplexClient(
    client_id='agent'+str(client),
    host='localhost',
    port=6379,
)
print(dir(logger))

logger.info('client', client)
logger.info7('client', client)
logger.error('this', client, 'an', 'error')
try:
    1/0
except Exception as e:
    logger.exception('myexc', client, 'yo', exc=e)
logger.section('yoyoyoo', sep='%')
logger.criticalfmt('Client format {:0>5d} - {:?<9}', client*100, 'foo')
logger.debug5fmt('debugger {:0>5d} - {:?<9}', 10+client, 'yo')

print(inspect.getdoc(logger.info7))
print(inspect.getdoc(logger.debug3))
