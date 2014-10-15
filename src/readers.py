#coding:utf-8
import struct
from collections import namedtuple
from StringIO import StringIO

from errors import ReachStreamEnd
from core.data import DataTypeMixIn, PrettyReaderMixIn, StringIOProxy
from core.readers import StreamReader

import logging

logger = logging.getLogger('binder.chips')


Head = namedtuple('FLVHead', 'prefix version flag audio_flag video_flag data_offset')
#Tag  = namedtuple('Tag', 'seq type size timestamp ext stream_id data pre_size')

AUDIO_TAG = 8 
VIDEO_TAG = 9
META_DATA = 18


class Tag(object):
    
    TYPE_MAP = {
        9: 'video tag',
        8: 'audio tag',
        18: 'meta data',
    }
    
    def __init__(self, seq, t, size, timestamp, ext, stream_id, data, pre_size):
        self._seq = seq
        self._type = t
        self._size = size
        self._timestamp = timestamp
        self._ext = ext
        self._stream_id = stream_id
        self._data = data
        self._pre_size = pre_size

    def __repr__(self):
        return "<Tag(type:%s,size:%d,ext:%d,ts:%d)>" % (self.TYPE_MAP[self._type], self._size, self._ext, self._timestamp)

    def pack(self):
        fmt = '>B3B3BB3B'
        data = (self._type,) + conv24(self._size) + conv24(self._timestamp) + (self._ext,) + conv24(self._stream_id)
        ret = struct.pack(fmt, *data) 
        if self.data:
            ret += self.data
        ret += struct.pack('>I', self._pre_size)
        return ret

    @property
    def size(self):
        return self._size

    @property
    def type(self):
        return self._type

    @property
    def seq(self):
        return self._seq

    @property
    def timestamp(self):
        return (self._timestamp | self._ext << 24)

    @timestamp.setter
    def timestamp(self, value):
        self._ext = (value >> 24 & 0xff)
        self._timestamp = (value & 0xffffff)

    @property
    def stream_id(self):
        return self._stream_id

    @property
    def data(self):
        return self._data

    @property
    def pre_size(self):
        return self._pre_size

    @property
    def is_keyframe(self):
        if self._type != 9: return False
        r, = struct.unpack_from('>B', self._data)
        return (r >> 4) == 1
        

def conv24(int24):
    high = (int24 >> 16)
    medium = (int24 >> 8) & 0xff
    low = int24 & 0xff
    return (high, medium, low)

def pack_head(a):
    """
    Head: prefix version flag data_offset empty
    """
    ret = struct.pack('>3sBBII', a.prefix, a.version, a.flag, a.data_offset, 0)
    return ret

def pack_tag(a):
    """
    Tag: seq type size timestamp ext stream_id data pre_size
    """
    return a.pack()

def flv_pack(a):
    return pack_head(a) if isinstance(a, Head) else pack_tag(a)


class RtmpStreamReader(StreamReader):

    FILE_FORMAT_FLV = 0 #flv file format
    FILE_FORMAT_F4V = 1 #f4v file format
    
    def __init__(self, stream):
        self.seq = 0
        self.file_format = RtmpStreamReader.FILE_FORMAT_FLV
        super(RtmpStreamReader, self).__init__(stream)

    def readHead(self):
        prefix      = 'F' + self.readRaw(2)
        version     = self.read8()
        flag        = self.read8()
        audio_flag  = flag & 0b100
        video_flag  = flag & 0b001
        data_offset = self.read32()
        self.read32() #ignore first 0 
        return Head(prefix, version, flag, audio_flag, video_flag, data_offset)
    
    def readTag(self, seq, tag_type, flag):
        tagType           = tag_type
        dataSize          = self.read24()
        timestamp         = self.read24()
        timestampExtended = self.read8()
        streamID          = self.read24()
        data = None
        if flag:
            data = self.readRaw(dataSize)
        else:
            self.readRaw(dataSize)
        size              = self.read32()
        return Tag(seq, tagType, dataSize, timestamp, timestampExtended, streamID, data, size)
        
    def next(self, flag=True):
        try:
            c = self.readRaw(1)
            if c == 'F':
                return self.readHead()
            self.seq += 1
            return self.readTag(self.seq, ord(c), flag)
        except:
            raise StopIteration

    def __iter__(self):
        return self


__all__ = ['Head', 'Tag', 'conv24', 'pack_head', 'pack_tag', 'flv_pack', 'RtmpStreamReader', 'AUDIO_TAG', 'VIDEO_TAG', 'META_DATA']
