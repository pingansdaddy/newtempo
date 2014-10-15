#coding:utf-8
import os

APP_HOME = '/root/newtempo'

LIVE_ROOT = os.path.join(APP_HOME, 'data', 'liveroot', 'channels')

NOTIFY_ADDRESS = [('127.0.0.1', 3334)]


#growing file dir
GROWING_FILE_DIR = os.path.join(APP_HOME, 'data','tdlive')
# cared suffix
GROWING_FILE_SUFFIX = '.flv'
#httpd server port
HTTPD_SRC_SER_PORT = 20000
#growingfile check frequency
TIMER_INTERVAL = 1


#Memory Fragment Step length
MEMORY_FRAGMENT_STEP_LENGTH = 5
#Max Pending times
MAX_INACTIVE_TIMES = 5

MAX_SUB_PIECE_SIZE = 10 * 1024 # 0x2800

NEXT_REQ_DELAY_TIME = 2000
DEFAULT_RETURN_BYTES = (2 * 1024 * 1024 * (NEXT_REQ_DELAY_TIME/1000))/8

#Vod 资源文件，支持伪206请求
VOD_RES_DIR = os.path.join(APP_HOME, 'data')
VOD_RES_SUFFIX = '.flv'
