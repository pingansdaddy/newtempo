from collections import namedtuple
from core.readers import StreamReader

from StringIO import StringIO


Head = namedtuple('FLVHead', 'prefix version flag audio_flag video_flag data_offset')

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

class ScriptDataReader(StreamReader):

    def __init__(self, stream):
        self.seq = 0
        super(ScriptDataReader, self).__init__(stream)

    def readScriptDataString(self, isLong=False):
        return (isLong) and self.readString16() or self.readString8()

    def readScriptDataValue(self):
        t = self.read8()
        value = None
        if t==0:
            print "here0"
            pass
        elif t==1:
            value = self.read8()
        elif t==2:
            value = self.readScriptDataString()
        elif t==3:
            print "here1"
        elif t==7:
            value = self.read16()
        elif t==8:
            self.read32()
            print "here2"
        elif t==10:
            print "array"
            arrayLength = self.read32()
            value = []
            while arrayLength:
                arrayLength -= 1
                value.append(self.readScriptDataValue())
        elif t==11:
            print "here3"
            value = self.read8()
            self.read16()
        elif t==12:
            value = self.readScriptDataString(True)
        else:
            print "here4"
            value = self.readScriptDataString()
        return value

    def objectEnd(self):
        oldPos = self.position()
        a = self.read8()
        b = self.read8()
        c = self.read8()
        self.reset(oldPos)
        return ((a == 0) and (b == 0) and (c == 9))

fs = open("/mnt/hgfs/res/jiaojing.f4v", "rb")
dr = RtmpStreamReader(fs)
head = dr.next(False)
print head
tag0 = dr.next(True)
print "tag=%r" % (tag0)

sr = ScriptDataReader(StringIO(tag0.data))
t  = sr.read8()
assert(t == 2)
t  = sr.read8()
assert(t == 0)
name = sr.readScriptDataString()
assert(name == "onMetaData")
#t = sr.read8()
#assert(t == 8)
#
#ecmaArrayLength = sr.read32()
#print "length=%d" % ecmaArrayLength

while (not sr.objectEnd()):
    propertyName = sr.readScriptDataValue()
    if "keyframes" == propertyName:
        pass
    elif "filesize" == propertyName:
        pass
    elif "hasKeyframes" == propertyName:
        pass
    elif "hasVideo" == propertyName:
        pass
    elif "hasAudio" == propertyName:
        pass
    elif "width" == propertyName:
        pass
    elif "height" == propertyName:
        pass
    else:
        print "nothing"

sr.close()

fs.close()
print "OK"
