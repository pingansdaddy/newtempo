#coding:utf-8
import struct
from zope.interface import Interface


SYSTEM_ENDIAN = None


__all__ = ['IPrettyBitReader', 'I24BitReader', 'I7BitReader', 'ITextReader', 'DataTypeMixIn', 'PrettyReaderMixIn', 'StringIOProxy']


class IPrettyBitReader(Interface):

    def readRaw(size):
        """
        Read x bit with specific size.
        """
    def read8():
        """
        Read 8 bit integer.
        """
    def read16():
        """
        Read 16 bit integer.
        """
    def read32():
        """
        Read 32 bit integer.
        """

class I24BitReader(Interface):

    def read24():
        """
        Todo:??
        """

class I7BitReader(Interface):

    def read7BitValue():
        """
        Todo: What does the 7bit value means.
        """
    
class ITextReader(Interface):
    
    def readString8():
        """
        First 8bit integer as length of String. Second read the string.
        """
    def readString16():
        """
        First 16bit integer as length of String. Second read the string.
        """
    def readString():
        """
        First 7bit value integer as length of String. Second read the string.
        """

class DataTypeMixIn(object):

    #: Network byte order
    ENDIAN_NETWORK = "!"
    #: Native byte order
    ENDIAN_NATIVE = "@"
    #: Little endian
    ENDIAN_LITTLE = "<"
    #: Big endian
    ENDIAN_BIG = ">"

    endian = ENDIAN_NETWORK

    def _is_big_endian(self):
        """
        Whether the current endian is big endian.
        """
        if self.endian == DataTypeMixIn.ENDIAN_NATIVE:
            return SYSTEM_ENDIAN == DataTypeMixIn.ENDIAN_BIG

        return self.endian in (DataTypeMixIn.ENDIAN_BIG, DataTypeMixIn.ENDIAN_NETWORK)

    def read_uchar(self):
        """
        Reads an C{unsigned char} from the stream.
        """
        return ord(self._read(1))

    def read_ushort(self):
        """
        Reads a 2 byte unsigned integer from the stream.
        """
        return struct.unpack("%sH" % self.endian, self._read(2))[0]

    def read_24bit_uint(self):
        """
        Reads a 24 bit unsigned integer from the stream.

        @since: 0.4
        """
        order = None

        if not self._is_big_endian():
            order = [0, 8, 16]
        else:
            order = [16, 8, 0]

        n = 0

        for x in order:
            n += (self.read_uchar() << x)

        return n

    def read_utf8_string(self, length):
        """
        Reads a UTF-8 string from the stream.

        @rtype: C{unicode}
        """
        s = struct.unpack("%s%ds" % (self.endian, length), self._read(length))[0]

        return s.decode('utf-8')

    def read_long(self):
        """
        Reads a 4 byte integer from the stream.
        """
        return struct.unpack("%sl" % self.endian, self._read(4))[0]

class PrettyReaderMixIn(object):
    
    def read8(self):
        return self.read_uchar()

    def read16(self):
        return self.read_ushort()

    def read24(self):
        return self.read_24bit_uint()

    def read32(self):
        return self.read_long()

    def readRaw(self, n):
        return self._read(n)

class StringIOProxy(object):
    
    def __init__(self, obj=None):
        self._obj = obj
        self.total_bytes = 0
        self._buf = ''

    def _read(self, n):
        data = self._obj.read(n)
        self._buf += data
        self.total_bytes += n
        return data

    def empty_buffer(self):
        """
        Todo: Temporary use.
        """
        data = self._buf
        self._buf = ''
        return data

    @property
    def position(self):
        return self._obj.tell()
