from test.common import *
import traceback
import io


logger = LoggerplexClient(
    client_id='agent1',
    host='localhost',
    port=6379,
)

logger.info('my', 'value', 'is', 'shit')
logger.error('this', 34, 'an ', 'error')
try:
    1/0
except Exception as e:
    print(e.__traceback__)
    logger.exception('exc', 34, 'yo', exc=e)
logger.section('yoyoyoo', sep='%')
logger.critical('My format {:0>5d} - {:?<9}'.format(234, 'shit'))
logger.debug('debugger {:0>5d} - {:?<9}'.format(17, 'yo'))
