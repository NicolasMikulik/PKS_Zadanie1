import socket

# Create a UDP socket
import struct

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Bind the socket to the port
server_address = ('localhost', 10000)
print('starting up on {} port {}'.format(*server_address))
sock.bind(server_address)
data, server = sock.recvfrom(4096)
print('received {!r}'.format(data))
received_chunks = 0
rec_list = []
while True:
    data, addr = sock.recvfrom(65535)
    header = data[:18]
    data = data[18:]
    (mType, fragSize, fragIndex, fragCount, crc) = struct.unpack('!hIII', header)

    print(
        '\nTyp: ' + str(mType) +
        '\nFragSize: ' + str(fragSize) +
        '\nFragIndex: ' + str(fragIndex) +
        '\nFragCount: ' + str(fragCount) +
        '\nCRC: ' + str(crc)
    )

    if len(rec_list) < fragCount:
        need_to_add = fragCount - len(rec_list)
        rec_list.extend([''] * need_to_add)  # empty list for messages of size fragCount
    rec_list[fragIndex - 1] = data

    received_chunks += 1
    if received_chunks == fragCount:
        break  # This is where the second while loop ends

if mType == 3:
    content = b''.join(rec_list)
    f = open('output.txt', 'wb')
    f.write(content)
