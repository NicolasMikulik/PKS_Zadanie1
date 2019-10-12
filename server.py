import socket
import sys
from struct import *

# Create a UDP socket
import struct
try:
    mysocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print("Socket created")
except socket.error:
    print("Failed to create socket")
    exit()
server_address = ('localhost', 8484)
try:  # Bind the socket to the port
    mysocket.bind(server_address)
    print('Starting up on {} port {}'.format(*server_address)+ ". Waiting for fragment size.")
except socket.error:
    print("Failed to bind socket")
struct_header_size = calcsize('BHHH')
address_size = sys.getsizeof(server_address)
save_path = "/home/nicolas/PycharmProjects/pks_zadanie1"
fragSize_msg = mysocket.recvfrom(512)
mysocket.sendto("Roger".encode(), fragSize_msg[1])
fragSize = int(fragSize_msg[0].decode())
received_file = bytearray()
print("Client set fragment size to: "+str(fragSize))
received_frag = 0
while True:
    dataStream = mysocket.recvfrom(fragSize+struct_header_size+address_size)
    data = dataStream[0]
    addr = dataStream[1]
    header = data[:8]
    reply = "Server_Reply: " + str(len(data)) + " characters received"
    mysocket.sendto(reply.encode(), addr)
    print("Message["+addr[0]+"] - "+data[8:].decode().strip())
    received_file += data[8:]
    print(received_file.decode())
    (msg_type, data_length, frag_index, frag_count) = struct.unpack('BHHH', header)
    print(msg_type, data_length, frag_index, frag_count)
    received_frag += 1
    if received_frag == frag_count:
        print("All data received")
        break
if msg_type == 1:
    write_file = open('/home/nicolas/PycharmProjects/pks_zadanie1/received.txt', 'wb')
    write_file.write(received_file)
    write_file.close()
mysocket.close()
