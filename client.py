import math
import socket
import struct
from binascii import crc32
# Create a UDP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

server_address = ('localhost', 10000)
print('starting up on {} port {}'.format(*server_address))
message = b'This is our message. It will be sent all at once'
sock.sendto(message,server_address)
fragIndex=0 #reset fragment indexing
fragSize = int(input('Fragment size: '))

file_name = "/home/nicolas/PycharmProjects/Coursera Assignments/romeo.txt"
f=open(file_name,"rb")
contents = f.read()
fragCount = math.ceil(len(contents) / fragSize)

while contents:
    data = bytearray()
    data.extend(contents[:fragSize])
    fragIndex += 1
    crc = crc32(data)
    header = struct.pack('!hlll', 3, fragSize, fragIndex, fragCount, crc)
    sock.sendto(header + bytearray(data), server_address)
    contents = contents[fragSize:]

print('closing socket')
sock.close()
