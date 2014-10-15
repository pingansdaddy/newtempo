#coding:utf-8
import os, sys, struct, socket, time, traceback, urllib, json
from StringIO import StringIO
from optparse import make_option, OptionParser
from readers import Head, Tag
from readers import AUDIO_TAG, VIDEO_TAG, META_DATA
from readers import pack_head, pack_tag
from errors import FragmentError
from readers import RtmpStreamReader

from util.closure import id_generator
import logging
import config


logger = logging.getLogger('binder.chips')


class ReportMixin(object):

    TRACKER_HOSTS = config.NOTIFY_ADDRESS

    def __init__(self): 
        """ 初始化一个发送UDP包的套接字 """
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send(self, data):
        for tracker in self.TRACKER_HOSTS:
            self.sock.sendto(data, tracker)
    
    def report(self, src_id, current_chunk_id, mini_chunk_id=0):
        fmt = '!H%dsII' % len(src_id)
        data = struct.pack(fmt, len(src_id), src_id, current_chunk_id, mini_chunk_id)
        self.send(data)

    def notify(self, channel, tag_seq, chunk_seq, last_tag_timestamp, chunk_id, step_length):
        fmt = '!H%ds4IB' % (len(channel),)
        data = struct.pack(fmt, len(channel), channel, tag_seq, chunk_seq, last_tag_timestamp, chunk_id, step_length)
        self.sock.sendto(data, ('127.0.0.1', 3335))


class Fragment(object):
    """
    Slice flv data stream into pieces.
    """

    def __init__(self, data_in=None, step_length=1, channel=None, start_chunk_id='-0x1', delay_seconds = 0, enable_backswing=0):
        """
        @data_in: Data source.
        @step_length: The max length of time slices can play.
        @channel: The name of the data source.
        @start_chunk_id: Number of the starting chunk, starting from the current time by default.
        """
        if not channel:
            raise FragmentError('Channenl is required.')
        self._channel = channel
        if not data_in:
            data_in = sys.stdin
        elif data_in.startswith("rtmp://"):
            import librtmp
            conn = librtmp.RTMP(data_in, live=True)
            # Attempt to connect
            conn.connect()
            # Get a file-like object to access to the stream
            stream = conn.create_stream()
            # Read 1024 bytes of data
            data_in = stream

        self._buf = [] #store tag temporary.
        self._id_generator = id_generator(int(start_chunk_id, 16))

        self._stream = RtmpStreamReader(data_in) #data source reader.
        self._step_length = step_length

        self.delay_seconds = delay_seconds

        self._seq = 0 #sequence number of tag.
        self._chunk_seq = 0 #sequence number of chunk.
        self._skip_meta = self._skip_head = self._skip_magic_head = False
        self._flv_head_no = 0

        self._swing = 0 # swing
        self._head  = None
        
        self._skip_audio_tag = self._skip_video_tag = False
        self._enable_backswing = enable_backswing

        self._do_sleep = False

        self._has_head = False
        self._meta_tag = None

    def get_sleep_mode(self):
        return self._do_sleep

    def set_sleep_mode(self, value):
        self._do_sleep = value

    sleep_mode = property(get_sleep_mode, set_sleep_mode)

    def get_enable_backswing(self):
        return self._enable_backswing
        
    def set_enable_backswing(self, value):
        self._enable_backswing = value

    enable_backswing = property(get_enable_backswing, set_enable_backswing)

    def get_channel(self):
        """
        Return the channel name.
        """
        return self._channel

    channel = property(get_channel)

    def get_auto_step_length(self):
        """
        Return the step length in 微秒.
        """
        return (self._step_length * 1000) + self.backswing

    auto_step_length = property(get_auto_step_length)

    def get_backswing(self):
        """
        反向摆动值.
        """
        return (self._swing * (-1))
    
    backswing = property(get_backswing)

    def get_length_of_play_time(self):
        """
        Caculate the length of play time avilable in temporary cache.
        """
        if len(self._buf) > 1:
            return self._buf[-1].timestamp - self._buf[0].timestamp
        return 0

    length_of_play_time = property(get_length_of_play_time)

    def get_stream_time(self):
        """
        Get the time of play stream.
        """
        return self._start_time + (self._chunk_seq * self._step_length)

    stream_time = property(get_stream_time)

    def measure(self):
        """
        Determine whether chunk generated at this time. If does, call method cut.
        """
        if self.length_of_play_time > self.auto_step_length:
            self._cut()

    def _cut(self):
        """
        Do generate a chunk from the temporary cache array. And then, clear the cache.
        """
        now = time.time() # Get time of now in seconds.
        chunk_id = self._id_generator() #Generate a number of chunk from the growth.
        self._chunk_seq += 1 #Increase the number of chunk sequence.
        self.on_chunk_generated(chunk_id, self._buf)
        self._clear()
        if self.enable_backswing:
            self._swing = now - self.stream_time #Compute the value of deference between the current time and the stream time.

    def _clear(self):
        """
        Clear the temporary cache.
        """
        self._buf = []

    def handle_magic_head(self, tag):
        """
        Catch the first audio tag and video tag in the stream.
        """
        #print("skip_audio_tag:%s  skip_video_tab:%s" % (self._skip_audio_tag, self._skip_video_tag))
        if self._has_head:
            return False

            
        if not self._skip_video_tag and tag.type == VIDEO_TAG:
            self._first_video_tag = tag
            self._skip_video_tag = True
            
        if not self._skip_audio_tag and tag.type == AUDIO_TAG:
            self._first_audio_tag = tag
            self._skip_audio_tag = True

        #return (not(self._skip_audio_tag or self._skip_video_tag))

        if self._head.audio_flag == 0:
            if self._skip_video_tag:
                self._has_head = True
                return False
        else:
            if self._skip_audio_tag and self._skip_video_tag:
                self._has_head = True
                return False
        return True

    def advance(self):
        """
        Get a slice of CPU time to run.
        """
        self._start_time = time.time() #Start time in seconds.
        
        if not self._skip_head: #First read from stream.
            try:
                tag = self._stream.next()
                if not isinstance(tag, Head):
                    raise FragmentError('Flv stream head not found!')
                self._head = tag
                self._skip_head = True
            except StopIteration:
                return
         
        for tag in self._stream:
            self._seq += 1 # Increase the number of Tag sequence.
            if isinstance(tag, Tag):
                # skip the Metadata in flv stream.
                if tag.type == META_DATA:
                    self._meta_tag = tag
                    #print(tag) <Tag(type:meta data,size:121,ext:0,ts:0)>  121 + 11 = 132
                    continue
                if not self.handle_magic_head(tag):
                    self._buf.append(tag)
                    self.measure() # Judge slice chunk.
            else: #todo: May be ingored
                raise FragmentError('Receive another flv head from stream!')
            if self._do_sleep: time.sleep(0.01)

    def on_chunk_generated(self, chunk_id, tag_array):
        """
        Implemented by subclass.
        """
        raise NotImplementedError('on_chunk_generated')

class DataHandler(object):
    
    def __init__(self, target):
        self._target_dir = target
    
    def write_chunk(self, chunk_id, data):
        self.do_write('%s/%s.data' % (self._target_dir, hex(chunk_id)[2:]), data)

    def write_flv_head(self, chunk_id, data):
        self.do_write('%s/%s.head' % (self._target_dir, hex(chunk_id)[2:]), data)
        
    def do_write(self, filename, data):
        with open(filename, 'w') as f: f.write(data)

class MultiMessageHandler(object):

    def __init__(self): 
        self.error_list = []

    def buildPublishBody(self, ch, message):

        o = { "liveid" : "test_%s"%ch, "message": [] }
        
        if self.error_list:
            for msg in self.error_list:
                o["message"].append(msg)
        o["message"].append(message)
        return json.dumps(o)    

    def report(self, ch, current_chunk_id, mini_chunk_id=0):
        """
        {"liveid":1,message:[ "message_info1" , "message_info2" ] }
        """
        body = self.buildPublishBody(ch, current_chunk_id)
        r = urllib.urlopen("http://lilychat-server/lilychat/publish", data=body)
        if r.getcode() == 200:
            self.error_list[:] = []
        else:
            print(body)
            self.error_list.append(current_chunk_id)
            

    def notify(self, channel, tag_seq, chunk_seq, last_tag_timestamp, chunk_id, step_length):
        pass


class RegularFragment(Fragment, DataHandler, MultiMessageHandler):

    def __init__(self, path, start_timestamp_num=-1, **kwargs):
        self._path = path
        self._skip_flv_head = False
        self._start_timestamp_num = start_timestamp_num
        Fragment.__init__(self, **kwargs)
        DataHandler.__init__(self, path)
        MultiMessageHandler.__init__(self)

    def pack(self, tag):
        if type(tag) is str:
            return tag
        if self._start_timestamp_num > 0:
            tag.timestamp += self._start_timestamp_num
        return pack_tag(tag)
        #return tag if type(tag) is str else pack_tag(tag)
    
    def on_chunk_generated(self, chunk_id, tag_array):
        """
        Regular mode on chunk be generated.
        """
        if not self._skip_flv_head:
            #todo: pack flv head data
            data = pack_head(self._head)
            if self._meta_tag:
                data += pack_tag(self._meta_tag)
            if self._head.video_flag:
                data += pack_tag(self._first_video_tag)
            if self._head.audio_flag:
                data += pack_tag(self._first_audio_tag)
            self._flv_head_no = chunk_id - 1 #store head num to flv_head_no
            self.write_flv_head(self._flv_head_no, data)
            self._skip_flv_head = True
        data = reduce(lambda x, y: self.pack(x)+self.pack(y), tag_array)
        self.write_chunk(chunk_id, data)

        last_tag_timestamp = tag_array[-1].timestamp

        logger.info('src=%s,seq=%d,chunk_seq=%d,ts=%d,data_name=%s,step=%d' % (\
        self._channel, self._seq, self._chunk_seq, last_tag_timestamp,\
        hex(chunk_id)[2:], self._step_length))

        #==============Report===================================
        if hasattr(self, 'report'):
            #chunk_id = max(self._flv_head_no + 1, chunk_id - ( self.delay_seconds / self._step_length ))
            report_chunk_id = max(0, chunk_id - ( self.delay_seconds / self._step_length ))
            #self.report(self._channel, report_chunk_id, self._flv_head_no) #todo: mini chunk id have no report
            self.report(self._channel, hex(chunk_id)[2:], self._flv_head_no) #todo: mini chunk id have no report
            self.notify(self._channel, self._seq, self._chunk_seq, last_tag_timestamp, chunk_id, self._step_length)
        else:
            logger.warn("%s no report module" % self._channel)
        #==============Report===================================

def make_options():
    return [
        make_option('-r', '--resume', dest='start_id'),
        make_option('-d', '--delay', dest='delay_seconds'),
        make_option('-s', '--start_timestamp_num', type=int, dest='start_timestamp_num', default=-1),
        make_option('-l', '--step-length', type=int, dest='step_length'),
        make_option('-D', '--directory', dest='path'),
    ]


def buildRequestData(ch, d):
    o = {
            "liveid": "test_%s" % ch, 
            "config": 
                        { 
                            "starttime": int(time.time()), 
                        } 
        }

    o["config"].update(d) 
    return json.dumps(o)

def main():
    option_list = make_options()
    parser = OptionParser(option_list=option_list)
   
    (options, args) = parser.parse_args()

    kwargs = {}
    
    if options.start_id:
        kwargs['start_chunk_id'] = options.start_id

    if options.step_length:
        kwargs['step_length'] = options.step_length

    if options.delay_seconds:
        kwargs['delay_seconds'] = int(options.delay_seconds)

    if not options.path:
        parser.error('Path is required.')

    if not os.path.exists(options.path):
        parser.error('Path is not found.')

    if not len(args) == 1:
        parser.error('Wrong channel argument.')
    else:
        if args[0].startswith("rtmp://"):
            ch = os.path.basename(args[0])
            kwargs['channel'] = ch
            kwargs['data_in'] = args[0]
        else:
            kwargs['channel'] = args[0]
            ch = kwargs['channel']
    
    now = int(time.time())
    kwargs["start_chunk_id"] = "%s" % hex(now)
    fragment = RegularFragment(options.path, options.start_timestamp_num, **kwargs)
  
    kwargs["flv_head_no"] = "%s" % hex(now)[2:]
    d = buildRequestData(ch, kwargs)
    r = urllib.urlopen("http://lilychat-server/lilychat/set", data=d)
    if r.getcode() != 200:
        raise Error("call message system failed!")

    try:
        logger.info('Cut(%s) is running...' % (kwargs['channel'],))
        fragment.advance()
    except FragmentError, e:
        logger.info(str(e))
    except Exception, e:
        traceback.print_exc(file=sys.stderr)
        logger.info(str(e))
    else:
        logger.info('Total bytes %d' % (fragment._stream.position,))


__all__ = ['Fragment']


if __name__ == '__main__':
    main()
