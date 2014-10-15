#coding:utf-8
from twisted.trial import unittest
from chips.fragment import VodFragment
from chips.util import amf


class SliceFlvHeadTestCase(unittest.TestCase):
    
    def test_Slice_flv_head(self):
        stream = file('/home/yuanfang/workspace/tudou/chips/data/origin.flv')
        frag = VodFragment(stream)
        len1 = frag.slice_head()
        len2 = len(frag.flush())
        self.assertEqual(len1, len2)

    def test_Slice_flv_head(self):
        stream = file('/home/yuanfang/workspace/tudou/chips/data/aaa.flv')
        frag = VodFragment(stream)
        def handle_meta_data(tag):
            r = amf.AMF0(tag.data)
            assert "onMetaData" ==  r.read()
            obj = r.read()
            if obj['hasKeyframes']:
                keyframes = obj['keyframes']
                print dir(keyframes)
                print keyframes.filepositions
                print keyframes.times
            
        frag.onMetaData = handle_meta_data
        len1 = frag.slice_head()
        len2 = len(frag.flush())
        self.assertEqual(len1, len2)
