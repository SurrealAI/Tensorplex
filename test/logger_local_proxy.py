from test.common import *
from tensorplex import *


logger = LoggerplexServer('~/Temp/loggerplex', overwrite=1, debug=1)

client = 4

logproxy = logger.get_proxy(
    client_id='agent'+str(client),
)

logproxy.info('client', client)
logproxy.info7('client', client)
logproxy.error('this', client, 'an', 'error')
try:
    1/0
except Exception as e:
    logproxy.exception('exc', client, 'yo', exc=e)
logproxy.section('yoyoyoo', sep='%')
logproxy.critical('Client format {:0>5d} - {:?<9}', client * 100, 'foo')
logproxy.debug5('debugger {:0>5d} - {:?<9}', 10 + client, 'yo')

print(inspect.getdoc(logproxy.info7))
print(inspect.getdoc(logproxy.debug3))