#coding:utf-8
import os
import sys
import json
import traceback
import urlparse
from binascii import hexlify
from twisted.web import resource
from twisted.web import server
from twisted.web.error import NoResource
from twisted.internet import defer
from chips.fragment import VodFragment as Fragment
from chips import config
from chips import logging



logger = logging.getLogger('binder.chips')


test_page = """
<html>
<head>
    <title>Hello</title>
</head>
<body>
    <h2>%s</h2>
</body>
</html>
"""

def handle_api1_request(channel, shared_dict):
    if not shared_dict.has_key(channel):
        logger.info('API1 channel=%s not found!' % (channel,))
        return None
    meta = shared_dict[channel]
    data = {
        'code': 200,
        'brief': 'Success',
        'data': {
            'start':   meta['start'],
            'step':    meta['step'],
            'end':     meta['end'],
            'status':  meta['status'],
            'current': meta['start'] + (len(meta['chunks']) - 1),
        }
    }
    logger.info('API1 %s start=%d end=%d step=%d chunks=%d' % (channel, meta['start'], meta['end'], meta['step'], len(meta['chunks']))) 
    return defer.succeed(json.dumps(data))
    

def handle_api2_request(channel, seq, shared_dict):
    if not shared_dict.has_key(channel):
        logger.info('API2 channel=%s not found!' % (channel,))
        return None
    meta = shared_dict[channel]
    fd = meta['fd']
    chunks = meta['chunks']
    flv_head_no = meta['start']
    no = seq - flv_head_no
    try:
        chunk = chunks[no]
        start, offset = chunk
        os.lseek(fd, start, os.SEEK_SET)
        data = os.read(fd, offset)
        logger.info('API2 channel=%s seq=%d %d' % (channel, seq, offset)) 
        return defer.succeed(data)
    except IndexError, e:
        logger.error('API2 seq=%d not found!' % (no,))
        return None

class Root(resource.Resource):
    
    def __init__(self, shared_dict):
        resource.Resource.__init__(self)
        self.putChild('live', Live(shared_dict))

class Live(resource.Resource):
    
    def __init__(self, shared_dict):
        resource.Resource.__init__(self)
        self.putChild('api', API(shared_dict))


class API(resource.Resource):

    def __init__(self, shared_dict):
        resource.Resource.__init__(self)
        self.putChild('1', LiveAPI1(shared_dict))
        self.putChild('2', LiveAPI2(shared_dict))


class LiveAPI1(resource.Resource):
    
    def __init__(self, shared_dict):
        resource.Resource.__init__(self)
        self._shared_dict = shared_dict

    def getChild(self, name, request):
        if name:
            self._channel = name
            return self
        else:
            return NoResource('Not Implemented Error!')

    def _cb_render_GET(self, data, request):
        request.write(data)
        request.finish()

    def render(self, request):
        deferrd = handle_api1_request(self._channel, self._shared_dict)
        request.setHeader('Content-Type', 'text/x-json')      
        request.setHeader('Cache-Control', 'max-age=2592000')
        request.setHeader('Connection', 'keep-alive')
        if deferrd:
            deferrd.addCallback(self._cb_render_GET, request)
            return server.NOT_DONE_YET
        else:
            data = {
                'code': 500,
                'brief': 'Channel not found',
            }
            return json.dumps(data)


class LiveAPI2(resource.Resource):

    def __init__(self, shared_dict):
        resource.Resource.__init__(self)
        self._shared_dict = shared_dict

    def getChild(self, name, request):
        if name:
            return LiveAPI2Channel(name, self._shared_dict)
        return NoResource('Require channel name!')


class LiveAPI2Channel(resource.Resource):

    def __init__(self, channel, shared_dict):
        resource.Resource.__init__(self)
        self._ch = channel
        self._shared_dict = shared_dict

    def getChild(self, name, request):
        if name:
            try:
                seq = int(name)
                return LiveAPI2ChannelSeq(self._ch, seq, self._shared_dict)
            except:
                return NoResource('Seq format error!')

        
class LiveAPI2ChannelSeq(resource.Resource):

    def __init__(self, channel, seq, shared_dict):
        resource.Resource.__init__(self)
        self._ch = channel
        self._seq = seq
        self._shared_dict = shared_dict

    def _cb_render_GET(self, data, request):
        request.write(data)
        request.finish()
    
    def render(self, request):
        deferrd = handle_api2_request(self._ch, self._seq, self._shared_dict)
        if deferrd:
            request.setHeader('Content-Type', 'video/x-flv')      
            request.setHeader('Cache-Control', 'max-age=2592000')
            request.setHeader('Connection', 'keep-alive')
            deferrd.addCallback(self._cb_render_GET, request)
            return server.NOT_DONE_YET
        else:
            return NoResource('Chunk not found!').render(request)

class HealthCheck(resource.Resource):
    def render_GET(self, request):
        return "OK"
    
class CrossDomain(resource.Resource):
    isLeaf = True
    def render_GET(self, request):
        return """<cross-domain-policy><site-control permitted-cross-domain-policies="all"/><allow-access-from domain="*"/><allow-http-request-headers-from domain="*" headers="*"/></cross-domain-policy>"""

class BackDoor(resource.Resource):
    def __init__(self, notifier):
        self.notifier = notifier
        resource.Resource.__init__(self)

    def make_page(self):
        channels = ''
        for ch, o in self.notifier._shared_dict.items():
            if not channels: channels = "<ul title='live'>"
            channels += "<li>%s-->%s</li>" % (ch, 'status=%d size=%d'%(o.status,o.size()))
        if channels:
            channels += "</ul>"
        else:
            channels = "no channel."
        return """
<html>
    <body>
        <div id="submitPannel" style="background-color: green">
        <form name="ch" method="POST">
            <input type="text" name="channel" />
            <input type="submit" value="Submit" />
        </form>
        </div>
        <div id="knownList" style="">
            %(known_list)s
        </div>
    </body>
</html>""" % dict(known_list = channels)

    def render_GET(self, request):
        return self.make_page()

    def render_POST(self, request):
        try:
            channels = request.args.get('channel')
            for ch in channels:
                path = os.path.join(config.GROWING_FILE_DIR, ch + config.GROWING_FILE_SUFFIX)
                if os.path.exists(path) and not self.notifier.exists(path):
                    self.notifier.add(path)
        except:
            traceback.print_exc(file=sys.stderr)
        return self.make_page()


def channelId(self):                    
    ch = None                           
    if self.path:                       
        o = urlparse.urlparse(self.path)
        ch = o.path.lstrip('/')         
        pos = o.path.find('?')          
        if pos > 0:                     
            ch = ch[:pos-1]             
    return ch                           


class VodResource(resource.Resource):
    def __init__(self):
        self.vod_id = ''
        resource.Resource.__init__(self)

    def getChild(self, name, request):
        if name:
            self.vod_id = name
            return self
        else:
            return NoResource('Not Implemented Error!')

    def render_GET(self, request):
        request.setHeader('Content-Type', 'image/gif')
        request.setHeader('Cache-Control', 'max-age=2000')
        request.setHeader('Connection', 'close')
        try:
            v_path = os.path.join(config.VOD_RES_DIR, self.vod_id)
            if request.args.get('head', 0):
                frag = Fragment(file(v_path))
                frag.slice_head()
                return frag.flush()
            start = long(request.args.get('start')[0])
            offset   = long(request.args.get('length')[0])
            fd = os.open(v_path, os.O_RDONLY)
            os.lseek(fd, start, os.SEEK_SET)
            data = os.read(fd, offset)
            os.close(fd)
            return data
        except Exception, e:
            traceback.print_exc(file=sys.stderr)
            return str(e)
