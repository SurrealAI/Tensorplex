from tensorplex.logger import Logger


log = Logger.get_logger(
    'main',
    stream='out',
    show_level=True,
    format='{name} {asctime} {filename:>16s} {funcName}() {lineno} {levelname} ',
    time_format='dhm',
)

def f():
    log.info7('yo info7')
    log.critical('yo crit')

def g():
    log.info3('yo info3')
    log.warning('yo warn')

f()
g()
f()
