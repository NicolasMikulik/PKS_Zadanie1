import binascii
import socket
import struct
from struct import *


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


SYN = 1
ACK = 2
REJ = 4
FIN = 8
MSG = 16
FIL = 32
REQ = 64
UDP_HEAD = 8
IP_HEAD = 20
key = "10011001"


def receive_msg(mysocket, frag_size, client_address):
    pass


def receive_fil(mysocket, frag_size, client_address):
    struct_header_size = calcsize('BHHHH')
    info_header = struct.pack('BHHHH', (FIL + ACK), frag_size, 0, 0, 0)
    mysocket.sendto(info_header, client_address)
    received_file = bytearray()
    print("Client set fragment size to: " + str(frag_size))
    received_frag = 0
    received_list = list()
    corrupted_list = list()
    while True:
        mysocket.settimeout(5.0)
        data_stream = mysocket.recvfrom(frag_size + struct_header_size + UDP_HEAD)
        mysocket.settimeout(None)
        data = data_stream[0]  # addr = data_stream[1]
        header = data[:struct_header_size]
        received_list.append(b'')  # received_file += data[struct_header_size:]
        (msg_type, data_length, frag_count, frag_index, crc) = struct.unpack('BHHHH', header)

        crc_check = binascii.crc_hqx(data[struct_header_size:])
        if crc_check == crc:
            print("Datagram nr. " + str(frag_index) + ": correct crc")
            reply_header = struct.pack('BHHHH', (FIL+ACK), 1, 1, frag_index, 0)
            mysocket.sendto(reply_header, client_address)
            received_list[frag_index] = data[struct_header_size:]
        else:
            print("---Datagram nr. " + str(frag_index) + ": INCORRECT crc---")
            reply_header = struct.pack('BHHHH', (FIL+REJ), 0, 1, frag_index, 0)
            corrupted_list.append(frag_index)
            mysocket.sendto(reply_header, client_address)
        received_frag += 1
        if received_frag == frag_count:
            print("Index of last received datagram was equal to number of all datagrams.")
            break
    data_stream = mysocket.recvfrom(struct_header_size + UDP_HEAD)
    (msg_type, data_length, frag_count, frag_index, info_crc) = struct.unpack('BHHHH', data_stream[0])
    if ((FIL + ACK), 1, 1, 1) == (msg_type, data_length, frag_count, frag_index):
        print("Client confirmed it has sent all datagrams")
    corr_received_file = b''.join(received_list)
    corr_write_file = open('/home/nicolas/PycharmProjects/pks_zadanie1/romeo_corrupted.txt', 'wb')
    corr_write_file.write(corr_received_file)
    corr_write_file.close()
    print("Number of corrupted datagrams ", len(corrupted_list), corrupted_list)
    if len(corrupted_list) != 0:
        info_header = struct.pack('BHHHH',(FIL + REJ + FIN), 1, 1, 1, 0)
        mysocket.sendto(info_header, client_address)
        print((FIL + REJ + FIN), "1, 1, 1, 0")
    if len(corrupted_list) != 0:
        while len(corrupted_list) > 0:
            requested_index = corrupted_list[0]
            print("Requesting datagram nr.", requested_index)
            reply_header = struct.pack('BHHHH', REQ, 0, 1, requested_index, 0)
            mysocket.sendto(reply_header, client_address)

            data_stream = mysocket.recvfrom(frag_size + struct_header_size + UDP_HEAD)
            data = data_stream[0]
            header = data[:struct_header_size]
            (reply_msg_type, reply_data_length, reply_frag_count, reply_frag_index, reply_crc) = struct.unpack('BHHHH',
                                                                                                               header)
            crc_check = binascii.crc_hqx(data[struct_header_size:])
            if crc_check == reply_crc:
                print("Received requested datagram nr.", reply_frag_index, "from client, correct CRC")
                received_list[reply_frag_index] = data[struct_header_size:]
                corrupted_list.pop(0)
                reply_header = struct.pack('BHHHH', (REQ+ACK), 1, 1, 1, 0)
                mysocket.sendto(reply_header, client_address)
            else:
                print("---Received requested datagram nr.", reply_frag_index, "INCORRECT CRC, requesting again...---")
                reply_header = struct.pack('BHHHH', (REQ+REJ), 0, 1, reply_frag_index, 0)
                mysocket.sendto(reply_header, client_address)
    else:
        reply_header = struct.pack('BHHHH', (FIL + ACK + FIN), 0, 0, 0, 0)
        mysocket.sendto(reply_header, client_address)
    received_file = b''.join(received_list)
    write_file = open('/home/nicolas/PycharmProjects/pks_zadanie1/romeo_copy19.txt', 'wb')
    write_file.write(received_file)
    write_file.close()
    print("Received file saved in location /home/nicolas/PycharmProjects/pks_zadanie1/romeo_copy19.txt")
    mysocket.close()
    pass


def become_server():
    try:
        mysocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        print("Server socket created")
    except socket.error:
        print("Failed to create server socket")
        exit()
    port = input("Please enter the number of port on which you want to be receiving data: ")
    port = 8484
    server_address = ('localhost', port)
    try:  # Bind the socket to the port
        mysocket.bind(server_address)
        print('Starting up on {} port {}'.format(*server_address) + ". Waiting for fragment size.")
    except socket.error:
        print("Failed to bind socket")

    struct_header_size = calcsize('BHHHH')
    init_info = mysocket.recvfrom(struct_header_size+UDP_HEAD)
    client_address = init_info[1]
    (init_type, frag_size, init_count, init_index, init_crc) = struct.unpack('BHHHH', init_info[0])
    if init_type == (MSG+SYN):
        receive_msg(mysocket, frag_size, client_address)
    if init_type == (FIL+SYN):
        receive_fil(mysocket, frag_size, client_address)



def become_client():
    pass

role = input("Do you wish to be a receiver?[Y/n]")
if(role == "Y" or role == "y"):
    become_server()
else:
    become_client()
'''
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


struct_header_size = calcsize('BHHHH')
frag_size_msg = mysocket.recvfrom(512)
mysocket.sendto("Roger".encode(), frag_size_msg[1])
frag_size = int(frag_size_msg[0].decode())
received_file = bytearray()
print("Client set fragment size to: " + str(frag_size))
received_frag = 0
received_list = list()
corrupted_list = list()
while True:
    mysocket.settimeout(5.0)
    data_stream = mysocket.recvfrom(frag_size + struct_header_size + UDP_HEAD)
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
data_stream = mysocket.recvfrom(struct_header_size + UDP_HEAD)
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

        data_stream = mysocket.recvfrom(frag_size + struct_header_size + UDP_HEAD)
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
'''