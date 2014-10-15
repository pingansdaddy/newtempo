#coding:utf-8
import os
import time



class GrowingFile(object):
    
    def __init__(self, fn):
        self._fn = fn
        self._fd = os.open(self._fn, os.O_RDONLY)
        self._max_size = 1024*4

    def run(self):
        
        while True:
            buf = os.read(self._fd, self._max_size)
            if not buf:
                continue
                
            time.sleep(0.01)


class Tailer(object):
    """
    与tail命令类似，输出跟踪文件的新行
    """
    def __init__(self, filename):
        self._fn = filename
        self._fd = os.open(self._fn, os.O_RDONLY)
        _stat = os.stat(self._fn)
        self.st_ino = _stat.st_ino
        os.lseek(self._fd, _stat.st_size, os.SEEK_SET)
        
    def handle_line(self, content):
        """
        override in child class
        """
        pass

    def do_rotate(self):
        try:
            os.close(self._fd)
            self._fd = os.open(self._fn, os.O_RDONLY)
        except Exception, e:
            pass

    def handle_fd_changed(self):
        c_ino = self.st_ino
        count = 0
        while c_ino == self.st_ino:
            try:
                c_ino = os.stat(self._fn).st_ino
                count += 1
            except OSError:
                time.sleep(1)
            if count > 5:
                break
        else:
            self.st_ino = c_ino
            self.do_rotate()

    def readline(self):
        buf = []
        while True:
            c = os.read(self._fd, 1)
            if c and c != '\n':
                buf.append(c)
            else:
                return ''.join(buf) if buf else None

    def advance(self):
        line = self.readline()
        if not line:
            self.handle_fd_changed()
            line = self.readline()
        
        if line:
            self.handle_line(line)
