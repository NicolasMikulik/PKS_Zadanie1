import math
import socket
import struct
import sys
import binascii


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


def encode_data(client_data, client_key):
    l_key = len(client_key)
    appended_data = client_data + '0' * (l_key - 1)
    remainder = mod2div(appended_data, client_key)
    codeword = client_data + remainder
    return codeword


def decode_data(data, key):
    l_key = len(key)
    appended_data = data + '0' * (l_key - 1)
    remainder = mod2div(appended_data, key)
    return remainder


# koniec funkcii pre crc


def construct_reply(re_msg_type, re_data_length, re_frag_count, re_frag_index):
    reply_string = str(re_msg_type) + str(re_data_length) + str(re_frag_count) + str(re_frag_index)
    reply_string = "{0:b}".format(int(reply_string))
    reply_crc = encode_data(reply_string, key)
    reply_crc = int(reply_crc[-(len(key) - 1):], 2)
    return struct.pack('BHHHH', re_msg_type, re_data_length, re_frag_count, re_frag_index, reply_crc)


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
read_file = "/home/nicolas/Pictures/icon.ico"
server_address = ('localhost', 8484)
address_size = sys.getsizeof(server_address)  # print(str(sys.getsizeof(server_address)))
reply_header_size = struct.calcsize('BHHHH')
msg_type = 1
data_length = 0
frag_index = 0
key = "10011001"
frag_size = 1450  # input("Enter fragment size: ")
mysocket.sendto(str(frag_size).encode(), server_address)
print(mysocket.recvfrom(512)[0].decode())
file = open(read_file, "rb")
contents = file.read()
read_contents = contents[0:]
file_size = len(contents)
frag_count = math.ceil(file_size / int(frag_size))
print("File of size " + str(file_size) + " is being sent in " + str(frag_count) + " datagrams")
corrupted_list = list()
while contents:
    data = bytearray()
    data.extend(contents[:frag_size])
    data_length = len(data)
    data_as_string = bin(int(binascii.hexlify(data), 16))
    if frag_index % 3 != 0:
        crcstr = encode_data(data_as_string[2:], key)
        crc = int(crcstr[-(len(key) - 1):], 2)
    else:
        data = data[2:]
        print("Intentionally sending smaller datagram ", len(data))
        crcstr = encode_data(data_as_string[4:], key)
        crc = int(crcstr[-(len(key) - 1):], 2)
    header = struct.pack('BHHHH', msg_type, data_length, frag_count, frag_index, crc)
    mysocket.sendto(header + bytearray(data),
                    server_address)  # print("Datagram sent, awaiting response from server...")

    data_stream = mysocket.recvfrom(address_size + reply_header_size)  # receives only header
    reply_data = data_stream[0]
    (reply_msg_type, reply_data_length, reply_frag_count, reply_frag_index, reply_crc) = struct.unpack('BHHHH',
                                                                                                       reply_data)
    reply_crcstr = "{0:b}".format(reply_crc)
    if len(reply_crcstr) < (len(key) - 1):
        reply_crcstr = '0' * ((len(key) - 1) - len(reply_crcstr)) + reply_crcstr
    reply_string = str(reply_msg_type) + str(reply_data_length) + str(reply_frag_count) + str(reply_frag_index)
    reply_string = "{0:b}".format(int(reply_string)) + reply_crcstr
    reply_check = decode_data(reply_string, key)
    temp = "0" * (len(key) - 1)
    if reply_check == temp:
        notification = "Server response: "
        if reply_data_length == 1:
            notification += "datagram nr. " + str(frag_index) + " arrived successfully."
        else:
            print("Server response: CORRUPTED datagram", reply_frag_index)
            corrupted_list.append(reply_frag_index)
            notification += "datagram nr. " + str(
                reply_frag_index) + " arrived corrupted and will be resent after delivery of other datagrams."
    print(notification)
    contents = contents[frag_size:]
    frag_index += 1
print("All datagrams sent, informing server...", corrupted_list)
if msg_type == 1:
    info_header = construct_reply(1, 1, 1, 1)
    mysocket.sendto(info_header, server_address)

data_stream = mysocket.recvfrom(address_size + reply_header_size)
reply_data = data_stream[0]
(reply_msg_type, reply_data_length, reply_frag_count, reply_frag_index, reply_crc) = struct.unpack('BHHHH', reply_data)
if (reply_msg_type, reply_data_length, reply_frag_count, reply_frag_index) == (5, 0, 0, 0):
    print("Server response: All datagrams received successfully")
if (reply_msg_type, reply_data_length, reply_frag_count, reply_frag_index) == (5, 1, 1, 1):
    print("Server response: Corrupted datagrams detected, server is requesting them to be resent.")
    while len(corrupted_list) > 0:
        mysocket.settimeout(3.0)
        data_stream = mysocket.recvfrom(address_size + reply_header_size)
        reply_data = data_stream[0]
        (reply_msg_type, reply_data_length, reply_frag_count, reply_frag_index, reply_crc) = struct.unpack('BHHHH', reply_data)
        print("Client: Resending requested datagram nr.", reply_frag_index)
        item = 0
        contents = read_contents[0:]
        while item < reply_frag_index:
            contents = contents[frag_size:]
            item += 1
        data = bytearray()
        data.extend(contents[:frag_size])
        data_length = len(data)
        data_as_string = bin(int(binascii.hexlify(data), 16))
        crcstr = encode_data(data_as_string[2:], key)
        crc = int(crcstr[-(len(key) - 1):], 2)
        header = struct.pack('BHHHH', msg_type, data_length, frag_count, reply_frag_index, crc)
        mysocket.sendto(header + bytearray(data), server_address)

        data_stream = mysocket.recvfrom(address_size + reply_header_size)
        con_data = data_stream[0]
        (con_msg_type, con_data_length, con_frag_count, con_frag_index, con_crc) = struct.unpack('BHHHH', con_data)
        if (con_msg_type, con_data_length, con_frag_count, con_frag_index) == (4, 1, 1, 1):
            print("Server response: RESENT datagram nr." + str(reply_frag_index) + " received successfully")
            corrupted_list.remove(reply_frag_index)
            if len(corrupted_list) == 0:
                break
        if con_msg_type == 4 and con_data_length == 0 and con_frag_count == 1:
            print("Server response: RESENT datagram nr." + str(reply_frag_index) + " corrupted again")
print(len(corrupted_list), "corrupted datagrams left")
mysocket.close()
file.close()
