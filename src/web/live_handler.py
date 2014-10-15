#coding:utf-8
import os
import sys
import json
import traceback
import urlparse
from binascii import hexlify
from twisted.web import resource
from twisted.web import server
from twisted.web import http
from twisted.web.error import NoResource
from twisted.internet import defer
from chips import config
from chips import logging


logger = logging.getLogger('binder.chips')

MAX_PIECE_BYTES = 200 * 1024


class Root(resource.Resource):
    
    def __init__(self, shared_dict):
        resource.Resource.__init__(self)
        self.putChild('liveresource', LiveResource(shared_dict))

class LiveResource(resource.Resource):
    
    def __init__(self, shared_dict):
        self._shared_dict = shared_dict
        self.channel = None
        resource.Resource.__init__(self)

    def getChild(self, name, request):
        if name == '':
            return NoResource("Channel not found!")
        else:
            self.channel = name
            return self
    def render_GET(self, request):
        if not self._shared_dict.has_key(self.channel):
            return NoResource("Channel Not Found!").render(request)
        frag = self._shared_dict[self.channel]
        try:
            args    = request.args
            #peer_id = args['id'][0]
            start   = args.has_key('start') and int(args['start'][0]) or -1
            head    = args.has_key('head') and int(args.get('head')[0]) or 0
            offset  = args.has_key('offset') and int(args.get('offset')[0]) or config.DEFAULT_RETURN_BYTES
        except Exception, e:
            request.setHeader('Cache-Control', 'no-cache')
            return resource.ErrorPage(http.INTERNAL_SERVER_ERROR,'Query string format error',str(e)).render(request)
        if start < 0:
            request.setHeader('Cache-Control', 'no-cache')
        else:
            request.setHeader('Cache-Control', 'max-age=3600')
        frag = self._shared_dict[self.channel]
        flag = (head == 1)
        try:
            raw = frag.do(start=start, flag=flag, offset=offset)
        except Exception, e:
            request.setHeader('Cache-Control', 'no-cache')
            return resource.ErrorPage(http.INTERNAL_SERVER_ERROR,'Os Error',str(e)).render(request)
	return raw
