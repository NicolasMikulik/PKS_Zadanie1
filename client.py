import math
import socket
import struct
import sys

# Create a UDP socket
try:
    mysocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print("Client socket created")
except socket.error:
    print("Failed to create socket")
    exit()
read_file = "/home/nicolas/PycharmProjects/Coursera Assignments/romeo.txt"
server_address = ('localhost', 8484)
print(str(sys.getsizeof(server_address)))
msg_type = 1
data_length = 0
frag_index = 0
frag_size = 50  # input("Enter fragment size: ")
mysocket.sendto(str(frag_size).encode(), server_address)
print(mysocket.recvfrom(512)[0].decode())
file = open(read_file, "rb")
contents = file.read()
file.close()
file_size = len(contents)
frag_count = math.ceil(file_size / int(frag_size))
print("File of size " + str(file_size) + " is being sent in "+str(frag_count)+" datagrams")
while contents:
    data = bytearray()
    data.extend(contents[:frag_size])
    data_length = len(data)
    frag_index += 1
    header = struct.pack('BHHH', msg_type, data_length, frag_index, frag_count)
    mysocket.sendto(header + bytearray(data), server_address)
    print(mysocket.recvfrom(512)[0].decode())
    contents = contents[frag_size:]
mysocket.close()
