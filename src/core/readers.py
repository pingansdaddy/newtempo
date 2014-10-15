#coding:utf-8
from StringIO import StringIO
from zope.interface import Interface, implements
from data import DataTypeMixIn
from data import ITextReader, IPrettyBitReader, I24BitReader, I7BitReader


class BinaryReader(DataTypeMixIn):

    implements([IPrettyBitReader, I7BitReader, I24BitReader, ITextReader])
    
    #=======PrettyBitReader===========
    def readRaw(self, n):
        return self.read(n)

    def read8(self):
        return self.read_uchar()

    def read16(self):
        return self.read_ushort()

    def read32(self):
        return self.read_long()
    #=======24Bit Reader =============
    def read24(self):
        return self.read_24bit_uint()

    #=======7Bit  Reader==============
    def read7BitValue(self):
        raise NotImplementedError

    #=======Text Reader===============
    def readString8(self):
        return self.readRaw(self.read8())

    def readString16(self):
        return self.readRaw(self.read16())

    def readString(self):
        return self.readRaw(self.read7BitValue())


class StreamReader(BinaryReader):
    
    def __init__(self, stream):
        self._iostream = stream if hasattr(stream, 'read') else StringIO(str(stream))

    def read(self, n):
        return self._iostream.read(n)

    def _read(self, n):
        """
        兼容DataTypeMixIn
        """
        return self.read(n)

    def reset(self, pos):
        self._iostream.seek(pos)
        
    def position(self):
        return self._iostream.tell()

    def close(self):
        self._iostream.close()
