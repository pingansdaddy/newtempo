import librtmp

# Create a connection
#conn = librtmp.RTMP("rtmp://rtmp.live.tudou.com/flv/mcountdown", live=True)
conn = librtmp.RTMP("rtmp://www.scbtv.cn/live/new", live=True)
# Attempt to connect
conn.connect()
# Get a file-like object to access to the stream
stream = conn.create_stream()
# Read 1024 bytes of data
data = stream.read(1)
print(data)
if(data == 'F'):
    c = stream.read(1)
    print(c)
    c = stream.read(1)
    print(c)
    c = stream.read(1)
    print("@")
