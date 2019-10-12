import math
import socket
import struct
import sys
import binascii


def xor(a, b):
    result = []
    for i in range(1, len(b)):
        if a[i] == b[i]:
            result.append('0')
        else:
            result.append('1')
    return ''.join(result)


def mod2div(divident, divisor):
    pick = len(divisor)
    tmp = divident[0: pick]
    while pick < len(divident):
        if tmp[0] == '1':
            tmp = xor(divisor, tmp) + divident[pick]
        else:
            tmp = xor('0' * pick, tmp) + divident[pick]
        pick += 1
    if tmp[0] == '1':
        tmp = xor(divisor, tmp)
    else:
        tmp = xor('0' * pick, tmp)
    checkword = tmp
    return checkword


def encode_data(client_data, key):
    l_key = len(key)
    appended_data = client_data + '0' * (l_key - 1)
    remainder = mod2div(appended_data, key)
    codeword = client_data + remainder
    return codeword


'''key = "1000001"
valkey = "{:b}".format(int(key, 2))
getchar = "{:c}".format(int(key, 2))
print(getchar, valkey, "{0:b}".format(int(key, 2)), "{0:d}".format(int(key, 2)))'''
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
key = "1001"
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
    crc = encode_data(data, key)
    frag_index += 1
    header = struct.pack('BHHH', msg_type, data_length, frag_index, frag_count)
    mysocket.sendto(header + bytearray(data), server_address)
    print(mysocket.recvfrom(512)[0].decode())
    contents = contents[frag_size:]
mysocket.close()
