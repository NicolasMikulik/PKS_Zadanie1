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
reply_header_size = struct.calcsize('BBBHH')
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
corrupted_list = list()
while contents:
    data = bytearray()
    data.extend(contents[:frag_size])
    data_length = len(data)
    data_as_string = bin(int(binascii.hexlify(data), 16))
    # print(bin(int(binascii.hexlify(data), 16)))
    if frag_index != frag_count - 2:
        crcstr = encode_data(data_as_string[2:], key)
        crc = int(crcstr[-(len(key)-1):], 2)
    else:
        crcstr = encode_data(data_as_string[4:], key)
        crc = int(crcstr[-(len(key) - 1):], 2)
    print(crcstr[-(len(key)-1):], crc, data_as_string[2:])
    frag_index += 1
    header = struct.pack('BHHHH', msg_type, data_length, frag_index, frag_count, crc)
    mysocket.sendto(header + bytearray(data), server_address)
    # print("Datagram sent, awaiting response from server...")

    dataStream = mysocket.recvfrom(address_size+reply_header_size) # receives only header
    reply_data = dataStream[0]
    (reply_msg_type, reply_data_length, reply_frag_count, reply_frag_index, reply_crc) = struct.unpack('BBBHH', reply_data)
    reply_crcstr = "{0:b}".format(reply_crc)
    if len(reply_crcstr) < (len(key)-1):
        reply_crcstr = '0' * ((len(key) - 1) - len(reply_crcstr)) + reply_crcstr
    print(frag_index, reply_crcstr)
    reply_string = str(reply_msg_type) + str(reply_data_length) + str(reply_frag_count) + str(reply_frag_index)
    reply_string = (bin(int(reply_string, 16)))[2:] + reply_crcstr
    #print(reply_string)
    reply_check = decode_data(reply_string, key)
    temp = "0" * (len(key) - 1)
    if(reply_check == temp):
        print("Successfully obtained server response")
    print(reply_msg_type)
    contents = contents[frag_size:]
mysocket.close()
