from test.common import *
import traceback
import io

client = 4

logger = LoggerplexClient(
    client_id='agent'+str(client),
    host='localhost',
    port=6379,
)

logger.info('client', client)
logger.error('this', client, 'an', 'error')
try:
    1/0
except Exception as e:
    print(e.__traceback__)
    logger.exception('exc', client, 'yo', exc=e)
logger.section('yoyoyoo', sep='%')
logger.critical('Client format {:0>5d} - {:?<9}', client*100, 'foo')
logger.debug('debugger {:0>5d} - {:?<9}', 10+client, 'yo')
