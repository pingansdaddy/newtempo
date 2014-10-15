#coding:utf-8
import os, sys, time

class GrowingFile(object):
    
    def __init__(self, fn):
        self._fn = fn
        self._fd = os.open(self._fn, os.O_RDONLY)
        self._max_size = 1024

    def run(self):
        buf = ''
        while True:
            res = os.read(self._fd, self._max_size)
            if not res:
                continue
            buf += res
            if len(buf) < self._max_size:
                continue
            else:
                sys.stdout.write(buf)
                buf = ''
            time.sleep(0.01)


if __name__ == '__main__':
    try:
        fn = sys.argv[1]
        GrowingFile(fn).run()
    except KeyboardInterrupt:
        pass
