#coding:utf-8
import os, sys
import logging
import logging.config
from chips import config


log_config = os.path.join(config.APP_HOME, 'etc', 'logging.conf')


def setLogger(logger):
    """
    默认logger的Level是WARN, 因此需要设置为DEBUG
    """
    logger.setLevel(logging.DEBUG)

MODE = 0

if os.path.exists(log_config):
    logging.config.fileConfig(log_config)
else:
    MODE = 1
    FORMAT = "%(asctime)s -[%(name)s]%(levelname)s - %(message)s"
    logging.basicConfig(format=FORMAT)


def getLogger(name):
    logger = logging.getLogger(name)
    if MODE:
        setLogger(logger)
    return logger
