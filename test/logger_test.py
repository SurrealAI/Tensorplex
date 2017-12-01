from tensorplex.logger import Logger


log = Logger.get_logger(
    'main',
    stream='out',
    level='warning',
    show_level=True,
    format='{name} {asctime} {filename:>16s} {funcName}() {lineno} {levelname} ',
    time_format='dhm',
)

def f():
    log.info7fmt('yo {:.3f} info7', 1/17)
    log.criticalfmt('yo crit {:.2e} {}', 3**0.5, {'x':3})
    log.info7('yo {:.3f} info7', 1/17)
    log.critical('yo crit {:.2e} {}', 3**0.5, {'x':3})

def g():
    log.info3('yo info3')
    log.warning('yo warn')

f()
g()
f()
log.infosection('Yo', sep='!', repeat=50)
