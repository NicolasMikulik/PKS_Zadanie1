import socket
import sys
from struct import *
import binascii
# Zdroj funkcii xor(a, b), mod2div(divident, divisor) a decode_data(data, key) pre CRC:
# https://www.geeksforgeeks.org/cyclic-redundancy-check-python/
# Princip komunikacie servera a klienta:
# https://www.binarytides.com/programming-udp-sockets-in-python/?fbclid=IwAR2-JPM5O9EhroW-5WsBSzu-53NFYfqN54WqKIA8WcrJEWKmmX8gZrBo-4Y
# UDP s umiestnovanim datagramov do pola podla indexu datagramu:
# https://stackoverflow.com/questions/40325616/sending-file-over-udp-divided-into-fragments?noredirect=1&lq=1


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
        else:  # If leftmost bit is '0'
            tmp = xor('0' * pick, tmp) + divident[pick]
        pick += 1
    if tmp[0] == '1':
        tmp = xor(divisor, tmp)
    else:
        tmp = xor('0' * pick, tmp)
    checkword = tmp
    return checkword


def decode_data(data, key):
    l_key = len(key)
    appended_data = data + '0' * (l_key - 1)
    remainder = mod2div(appended_data, key)
    return remainder


def encode_data(client_data, client_key):
    l_key = len(client_key)
    appended_data = client_data + '0' * (l_key - 1)
    remainder = mod2div(appended_data, client_key)
    codeword = client_data + remainder
    return codeword

def construct_reply(re_msg_type, re_data_length, re_frag_count, re_frag_index):
    reply_msg_type = re_msg_type
    reply_data_length = re_data_length
    reply_frag_count = re_frag_count
    reply_frag_index = re_frag_index
    reply_string = str(reply_msg_type) + str(reply_data_length) + str(reply_frag_count) + str(reply_frag_index)
    reply_string = "{0:b}".format(int(reply_string))
    print(reply_string)
    reply_crc = encode_data(reply_string, key)
    reply_crc = int(reply_crc[-(len(key) - 1):], 2)
    print(reply_crc)
    return struct.pack('BBBHH', reply_msg_type, reply_data_length, reply_frag_count, reply_frag_index, reply_crc)


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

key = "1001"
struct_header_size = calcsize('BHHHH')
address_size = sys.getsizeof(server_address)
save_path = "/home/nicolas/PycharmProjects/pks_zadanie1"
fragSize_msg = mysocket.recvfrom(512)
mysocket.sendto("Roger".encode(), fragSize_msg[1])
fragSize = int(fragSize_msg[0].decode())
received_file = bytearray()
print("Client set fragment size to: "+str(fragSize))
received_frag = 0
received_list = list()
corrupted_list = list()
while True:
    dataStream = mysocket.recvfrom(fragSize+struct_header_size+address_size)
    data = dataStream[0]
    addr = dataStream[1]
    header = data[:struct_header_size]
    # received_file += data[struct_header_size:]
    (msg_type, data_length, frag_index, frag_count, crc) = struct.unpack('BHHHH', header)
    crcstr = "{0:b}".format(crc)
    if len(crcstr) < (len(key) - 1):
        crcstr = '0'*((len(key)-1) - len(crcstr)) + crcstr
    # print(crcstr, "{0:b}".format(crc))
    data_as_string = bin(int(binascii.hexlify(data[struct_header_size:]), 16))
    data_as_string = data_as_string[2:] + crcstr
    crccheck = decode_data(data_as_string, key)
    # print(crcstr, "{0:b}".format(crc), crccheck, data_as_string[:-3])
    temp = "0" * (len(key) - 1)
    if crccheck == temp:
        print("Correct crc")
        # reply = "Server_Reply: " + str(len(data[struct_header_size:])) + " bytes received successfully in datagram nr " + str(frag_index)
        reply_msg_type = 4
        reply_data_length = 1
        reply_frag_count = 1
        reply_frag_index = 1
        reply_string = str(reply_msg_type) + str(reply_data_length) + str(reply_frag_count) + str(reply_frag_index)
        reply_string = "{0:b}".format(int(reply_string))
        print(reply_string)
        reply_crc = encode_data(reply_string, key)
        reply_crc = int(reply_crc[-(len(key) - 1):], 2)
        print(reply_crc)
        # reply_header = struct.pack('BBBHH', reply_msg_type, reply_data_length, reply_frag_count, reply_frag_index, reply_crc)
        reply_header = construct_reply(4, 1, 1, 1)
        mysocket.sendto(reply_header, addr)
    else:
        print("---Incorrect crc---")
        corrupted_list.append(frag_index)
        reply_msg_type = 4
        reply_data_length = 0
        reply_frag_count = 1
        reply_frag_index = frag_index
        reply_string = str(reply_msg_type) + str(reply_data_length) + str(reply_frag_count) + str(reply_frag_index)
        reply_string = "{0:b}".format(int(reply_string))
        print(reply_string)
        reply_crc = encode_data(reply_string, key)
        reply_crc = int(reply_crc[-(len(key) - 1):], 2)
        # reply_header = struct.pack('BBBHH', reply_msg_type, reply_data_length, reply_frag_count, reply_frag_index, reply_crc)
        reply_header = construct_reply(4, 0, 1, frag_index)
        mysocket.sendto(reply_header, addr)
    received_frag += 1
    if received_frag == frag_count:
        print("All data received")
        break
    received_list.append(b'')
    received_list[frag_index-1] = data[struct_header_size:]
if msg_type == 1:
    received_file = b''.join(received_list)
    write_file = open('/home/nicolas/PycharmProjects/pks_zadanie1/icon_copy.ico', 'wb')
    write_file.write(received_file)
    write_file.close()
    print("Received file saved in location /home/nicolas/PycharmProjects/pks_zadanie1/icon_copy.ico")
mysocket.close()
