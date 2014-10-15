#coding:utf-8
import os, sys, struct
from readers import Head, Tag, pack_head
from readers import AUDIO_TAG, VIDEO_TAG, META_DATA
from readers import RtmpStreamReader
from chips import config


class Fragment(object):
    INIT     = 0 
    ACTIVE   = 1
    INACTIVE = 2
    def __init__(self, mode=False):
        self.mode = mode
        self.status = Fragment.INIT
        self.inactive_times = 0
        self._ptr = 0
    def advance(self):
	""" Get a slice of CPU time to run. """
        raise NotImplementedError("Fragment.advance")
    def measure(self):
        """ 决定是否分块的逻辑 """
        raise NotImplementedError("Fragment.measure")
    def inactive(self):
        if self.inactive_times == 0:
            self.status = Fragment.INACTIVE
        self.inactive_times += 1
    def active(self):
        self.status = Fragment.ACTIVE
        self.inactive_times = 0
    def size(self):
        raise NotImplementedError('Fragment.size()')
    @property
    def pointer(self):
        return (self._ptr - 1 ) % self.size()


class FlvFragment(Fragment):
    def __init__(self, fn, mode=True):
        stream = file(fn)
        self._fd = os.open(fn, os.O_RDONLY)
        self._reader = RtmpStreamReader(stream)
        self._pre_pos = 0
        self._skip_first_video_tag = False 
        self._first_video_tag = None
        self._head = None 
        self._keyframes = []
        self._skip_video_tag = False
        self._skip_first_audio_tag = False 
        self._first_audio_tag = None
        self._head_dead_line = 0
        super(FlvFragment, self).__init__(mode=mode)
        self._swig = 0
    def position(self):
        return self._reader.position()
    def get_keyframes(self):
        return self._keyframes
    keyframes = property(get_keyframes)
    def size(self):
        return len(self._keyframes)
    def append_keyframe(self, tag):
        self._keyframes.append((self._pre_pos, tag.timestamp))
        self._ptr = len(self._keyframes) - 1
        self._swig = 0 #init loop
    def incr(self, step):
        if self.pointer == self.size() - 1:
            self._ptr += 1
            self._swig = 0
        else:
            self._swig += step
            span = self.span()
            print 'cacle %d' % (span,)
            if self._swig > span:
                self._ptr += 1 
                print "increase ptr %d" % self._ptr
                self._swig -= span
    def span(self):
        if self.pointer >= self.size() - 1:
            return 0
        p = self.pointer
        a = self._keyframes[p][1]
        b = self._keyframes[p+1][1]
        return ((b - a)/1000)
        
    def advance(self):
        """
        Get a slice of CPU time to run.
        """
        in_bytes = self._pre_pos
        for tag in self._reader:
            if isinstance(tag, Tag):
                # skip the Metadata in flv stream.
                if not self.handle_magic_head(tag):
                    if tag.type == VIDEO_TAG and tag.is_keyframe:
                        self.append_keyframe(tag)
                self._pre_pos = self.position()
        in_bytes = self._pre_pos - in_bytes
        if in_bytes > 0:
            self.active()
        else:
            self.inactive()
    def handle_magic_head(self, tag):
        """
        Catch the first audio tag and video tag in the stream.
        """
        if not self._skip_video_tag and tag.type == VIDEO_TAG:
            self._first_video_tag = tag
            self._head_dead_line = self.position()
            self._skip_video_tag = True
        if not self._skip_first_audio_tag and tag.type == AUDIO_TAG:
            self._first_audio_tag = tag
            self._head_dead_line = self.position()
            self._skip_first_audio_tag = True
        return (not(self._skip_video_tag and self._skip_first_audio_tag))

    def do(self, start=-1, offset=None, flag=False, keyIndex=None):
        begin = end = 0
        current = keyIndex and keyIndex or self.pointer
        if start < 0: #从关键帧开始取数据
            begin = self._keyframes[current][0]
        else:
            begin = start
        end = offset and min(begin + offset, self.position()) or self.position()
        data_length = end - begin
        data = ''
        if data_length > 0:
            os.lseek(self._fd, begin, os.SEEK_SET)
            data = os.read(self._fd, data_length)
        else:
            raise OSError("Reach file end.")

        body = ''
        if flag:
            if not self._head and self._head_dead_line:
                os.lseek(self._fd, 0, os.SEEK_SET)
                self._head = os.read(self._fd, self._head_dead_line)
            body += struct.pack('>H%ds'%(len(self._head),), len(self._head), self._head)
        else:
            body += struct.pack('>H', 0)
        body += struct.pack('>QIH', begin, data_length, config.NEXT_REQ_DELAY_TIME)
        #filepositions
        temp = ''
        for (k,t) in self._keyframes:
            if k >= begin:
                temp += struct.pack('>QI', k, t)
            if k > end:
                break
        body += struct.pack('>I', len(temp)/12) + temp
        # insert head length
        body = struct.pack('>I', len(body)) + body + data
        return body

    def close(self):
        os.close(self._fd)
        self._reader.close()


class VodFragment(object):

    def __init__(self, stream):
        self._stream = RtmpStreamReader(stream)
        self._skip_meta = self._skip_head = self._skip_magic_head = False
        #self._skip_audio_tag = self._skip_video_tag = False
        self._skip_audio_tag = True
        self._skip_video_tag = False
        self._buf = []
        self.onMetaData = None

    def handle_magic_head(self, tag):
        """
        Catch the first audio tag and video tag in the stream.
        """
        if not self._skip_video_tag and tag.type == VIDEO_TAG:
            self._first_video_tag = tag
            self._skip_video_tag = True
        if not self._skip_audio_tag and tag.type == AUDIO_TAG:
            self._first_audio_tag = tag
            self._skip_audio_tag = True
        return (not(self._skip_audio_tag and self._skip_video_tag))
        #return (not(self._skip_audio_tag or self._skip_video_tag))
    
    def slice_head(self):
        for tag in self._stream:
            last_position = self._stream.position()
            self._buf.append(tag)
            if isinstance(tag, Tag):
                if tag.type == 18 and self.onMetaData:
                    self.onMetaData(tag)
                if not self.handle_magic_head(tag):
                    return last_position
        return last_position

    def flush(self):
        buf = ''
        for tag in self._buf:
            if isinstance(tag, Head):
                buf += pack_head(tag)
            else:
                buf += tag.pack()
        return buf
