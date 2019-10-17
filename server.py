import socket
import sys
from struct import *
import binascii
import struct
import time

# Zdroj funkcii xor(a, b), mod2div(divident, divisor) a decode_data(data, key) pre CRC:
# https://www.geeksforgeeks.org/cyclic-redundancy-check-python/
# Princip komunikacie servera a klienta:
# https://www.binarytides.com/programming-udp-sockets-in-python/?fbclid=IwAR2-JPM5O9EhroW-5WsBSzu-53NFYfqN54WqKIA8WcrJEWKmmX8gZrBo-4Y
# UDP s umiestnovanim datagramov do pola podla indexu datagramu:
# https://stackoverflow.com/questions/40325616/sending-file-over-udp-divided-into-fragments?noredirect=1&lq=1

# zaciatok funkcii pre crc zo zdroja https://www.geeksforgeeks.org/cyclic-redundancy-check-python/
def xor(a, b):
    result = []
    for i in range(1, len(b)):
        if a[i] == b[i]:
            result.append('0')
        else:
            result.append('1')
    return ''.join(result)


# koniec funkcii pre crc
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


# koniec funkcii pre crc


def construct_reply(re_msg_type, re_data_length, re_frag_count,
                    re_frag_index):  # vlastna funkcia pre vytvorenie hlavicky

    reply_string = str(re_msg_type) + str(re_data_length) + str(re_frag_count) + str(re_frag_index)
    reply_string = "{0:b}".format(int(reply_string))
    reply_crc = encode_data(reply_string, key)
    reply_crc = int(reply_crc[-(len(key) - 1):], 2)
    return struct.pack('BHHHH', re_msg_type, re_data_length, re_frag_count, re_frag_index, reply_crc)


try:
    mysocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print("Socket created")
except socket.error:
    print("Failed to create socket")
    exit()
server_address = ('localhost', 8484)
try:  # Bind the socket to the port
    mysocket.bind(server_address)
    print('Starting up on {} port {}'.format(*server_address) + ". Waiting for fragment size.")
except socket.error:
    print("Failed to bind socket")

key = "10011001"
struct_header_size = calcsize('BHHHH')
address_size = sys.getsizeof(server_address)
fragSize_msg = mysocket.recvfrom(512)
mysocket.sendto("Roger".encode(), fragSize_msg[1])
fragSize = int(fragSize_msg[0].decode())
received_file = bytearray()
print("Client set fragment size to: " + str(fragSize))
received_frag = 0
received_list = list()
corrupted_list = list()
while True:
    mysocket.settimeout(5.0)
    data_stream = mysocket.recvfrom(fragSize + struct_header_size + address_size)
    mysocket.settimeout(None)
    data = data_stream[0]
    addr = data_stream[1]
    header = data[:struct_header_size]
    received_list.append(b'')  # received_file += data[struct_header_size:]
    (msg_type, data_length, frag_count, frag_index, crc) = struct.unpack('BHHHH', header)
    crcstr = "{0:b}".format(crc)
    if len(crcstr) < (len(key) - 1):
        crcstr = '0' * ((len(key) - 1) - len(crcstr)) + crcstr
    data_as_string = bin(int(binascii.hexlify(data[struct_header_size:]), 16))
    data_as_string = data_as_string[2:] + crcstr
    crccheck = decode_data(data_as_string, key)
    temp = "0" * (len(key) - 1)
    if crccheck == temp:
        print("Datagram nr. " + str(frag_index) + ": correct crc")
        reply_header = struct.pack('BHHHH', 4, 1, 1, 1, 0)
        mysocket.sendto(reply_header, addr)
        received_list[frag_index] = data[struct_header_size:]
    else:
        print("---Datagram nr. " + str(frag_index) + ": INCORRECT crc---")
        reply_header = struct.pack('BHHHH', 4, 0, 1, frag_index, 0)
        corrupted_list.append(frag_index)
        mysocket.sendto(reply_header, addr)
    received_frag += 1
    if received_frag == frag_count:
        print("Index of last received datagram was equal to number of all datagrams.")
        break
data_stream = mysocket.recvfrom(struct_header_size + address_size)
(msg_type, data_length, frag_count, frag_index, info_crc) = struct.unpack('BHHHH', data_stream[0])
if (1, 1, 1, 1) == (msg_type, data_length, frag_count, frag_index):
    print("Client confirmed it has sent all datagrams")
    reply_header = struct.pack('BHHHH', 5, 1, 1, 1, 0)
    mysocket.sendto(reply_header, data_stream[1])
corr_received_file = b''.join(received_list)
corr_write_file = open('/home/nicolas/PycharmProjects/pks_zadanie1/icon_corrupted_copy.ico', 'wb')
corr_write_file.write(received_file)
corr_write_file.close()
print("Number of corrupted datagrams ", len(corrupted_list), corrupted_list)
if len(corrupted_list) != 0:
    while len(corrupted_list) > 0:
        requested_index = corrupted_list[0]
        print("Requesting datagram nr.", requested_index)
        reply_header = struct.pack('BHHHH', 5, 0, 1, requested_index, 0)
        mysocket.sendto(reply_header, addr)

        data_stream = mysocket.recvfrom(fragSize + struct_header_size + address_size)
        data = data_stream[0]
        header = data[:struct_header_size]
        (reply_msg_type, reply_data_length, reply_frag_count, reply_frag_index, reply_crc) = struct.unpack('BHHHH', header)
        crcstr = "{0:b}".format(reply_crc)
        if len(crcstr) < (len(key) - 1):
            crcstr = '0' * ((len(key) - 1) - len(crcstr)) + crcstr
        data_as_string = bin(int(binascii.hexlify(data[struct_header_size:]), 16))
        data_as_string = data_as_string[2:] + crcstr
        crccheck = decode_data(data_as_string, key)
        temp = "0" * (len(key) - 1)
        if crccheck == temp:
            print("Received requested datagram nr.", reply_frag_index,"from client, correct CRC")
            received_list[reply_frag_index] = data[struct_header_size:]
            corrupted_list.pop(0)
            reply_header = struct.pack('BHHHH', 4, 1, 1, 1, 0)
            mysocket.sendto(reply_header, addr)
        else:
            print("---Received requested datagram nr.", reply_frag_index, "INCORRECT CRC, requesting again...---")
            reply_header = struct.pack('BHHHH', 4, 0, 1, reply_frag_index, 0)
            mysocket.sendto(reply_header, addr)
else:
    reply_header = struct.pack('BHHHH', 5, 0, 0, 0, 0)
    mysocket.sendto(reply_header, addr)
if msg_type == 1:
    received_file = b''.join(received_list)
    write_file = open('/home/nicolas/PycharmProjects/pks_zadanie1/3_Rel_corrupted.pdf', 'wb')
    write_file.write(received_file)
    write_file.close()
    print("Received file saved in location /home/nicolas/PycharmProjects/pks_zadanie1/3_Rel_Prez_UDP_copy.pdf")
mysocket.close()
