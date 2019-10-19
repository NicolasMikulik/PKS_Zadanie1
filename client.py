import binascii
import math
import socket
import struct


# Zdroj funkcii xor(a, b), mod2div(divident, divisor) a decode_data(data, key) pre CRC:
# https://www.geeksforgeeks.org/cyclic-redundancy-check-python/
# Princip komunikacie servera a klienta:
# https://www.binarytides.com/programming-udp-sockets-in-python/?fbclid=IwAR2-JPM5O9EhroW-5WsBSzu-53NFYfqN54WqKIA8WcrJEWKmmX8gZrBo-4Y
# UDP s umiestnovanim datagramov do pola podla indexu datagramu:
# https://stackoverflow.com/questions/40325616/sending-file-over-udp-divided-into-fragments?noredirect=1&lq=1
# Kniznica pouzita pre crc16; polynom x^16+x^12+x^5+1, decimalna hodnota=69665, hexad. hodnota=11021
# https://docs.python.org/3/library/binascii.html


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


def become_server():
    pass


def send_msg(socket, server_IP, server_port):
    pass


def send_file(mysocket, server_IP, server_port):
    server_address = ('127.0.0.1', 8484)
    header_size = struct.calcsize('BHHHH')
    frag_size = int(input("Please enter maximum size of a datagram in bytes: "))
    if frag_size > (1500 - IP_HEAD - UDP_HEAD - header_size):
        frag_size = 1500 - IP_HEAD - UDP_HEAD - header_size
        print("Entered size of datagram was too large, size was set to the value of", frag_size, "bytes.")
    info_header = struct.pack('BHHHH', (FIL+SYN), frag_size, 0, 0, 0)
    mysocket.sendto(info_header, server_address)
    print("Server was informed that about sending a file and about datagram size.")
    server_reply = mysocket.recvfrom(header_size+UDP_HEAD)
    (reply_msg_type, reply_data_length, reply_frag_count, reply_frag_index, reply_crc) = struct.unpack('BHHHH',server_reply[0])
    if reply_msg_type == (FIL + ACK) and reply_data_length == frag_size:
        print("Server response: Prepared to receive file.")
    frag_index = 0
    read_file = "/home/nicolas/PycharmProjects/Coursera Assignments/romeo.txt"
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
        if frag_index != 7:
            crc = binascii.crc_hqx(data,0)
        else:
            data = data[2:]
            print("Intentionally sending smaller datagram ", len(data))
            crc = binascii.crc_hqx(data[1:],0)
        header = struct.pack('BHHHH', FIL, data_length, frag_count, frag_index, crc)
        mysocket.sendto(header + bytearray(data), server_address)  # print("Datagram sent, awaiting response from server...")
        data_stream = mysocket.recvfrom(header_size+UDP_HEAD)  # receives only header
        reply_data = data_stream[0]
        (reply_msg_type, reply_data_length, reply_frag_count, reply_frag_index, reply_crc) = struct.unpack('BHHHH',
                                                                                                           reply_data)
        notification = "Server response: "
        if reply_msg_type == (FIL + ACK):
            notification += "datagram nr. " + str(reply_frag_index) + " arrived successfully."
        if reply_msg_type == (FIL + REJ):
            print("---Server response: CORRUPTED datagram", str(reply_frag_index)+"---")
            corrupted_list.append(reply_frag_index)
            notification += "datagram nr. " + str(
                reply_frag_index) + " arrived corrupted and will be resent after delivery of other datagrams."
        print(notification)
        contents = contents[frag_size:]
        frag_index += 1
    print("All datagrams sent, informing server...", corrupted_list)
    info_header = struct.pack('BHHHH', FIL+ACK, 1, 1, 1, 0)
    mysocket.sendto(info_header, server_address)

    data_stream = mysocket.recvfrom(header_size+UDP_HEAD)
    reply_data = data_stream[0]
    (reply_msg_type, reply_data_length, reply_frag_count, reply_frag_index, reply_crc) = struct.unpack('BHHHH',
                                                                                                       reply_data)
    print(reply_msg_type, reply_data_length, reply_frag_count, reply_frag_index, reply_crc)
    if (reply_msg_type, reply_data_length, reply_frag_count, reply_frag_index) == ((FIL + ACK + FIN), 0, 0, 0):
        print("Server response: All datagrams received successfully")
    if (reply_msg_type, reply_data_length, reply_frag_count, reply_frag_index) == ((FIL + REJ + FIN), 1, 1, 1):
        print("Server response: Corrupted datagrams detected, server is requesting them to be resent.")
        while len(corrupted_list) > 0:
            # mysocket.settimeout(3.0)
            data_stream = mysocket.recvfrom(header_size+UDP_HEAD)
            reply_data = data_stream[0]
            (reply_msg_type, reply_data_length, reply_frag_count, reply_frag_index, reply_crc) = struct.unpack('BHHHH',
                                                                                                               reply_data)
            print("Client: Resending requested datagram nr.", reply_frag_index)
            item = 0
            contents = read_contents[0:]
            while item < reply_frag_index:
                contents = contents[frag_size:]
                item += 1
            data = bytearray()
            data.extend(contents[:frag_size])
            data_length = len(data)
            crc = binascii.crc_hqx(data, 0)
            header = struct.pack('BHHHH', REQ, data_length, frag_count, reply_frag_index, crc)
            mysocket.sendto(header + bytearray(data), server_address)

            data_stream = mysocket.recvfrom(header_size+UDP_HEAD)
            con_data = data_stream[0]
            (con_msg_type, con_data_length, con_frag_count, con_frag_index, con_crc) = struct.unpack('BHHHH', con_data)
            if (con_msg_type, con_data_length, con_frag_count, con_frag_index) == ((REQ+ACK), 1, 1, 1):
                print("Server response: RESENT datagram nr." + str(reply_frag_index) + " received successfully")
                corrupted_list.remove(reply_frag_index)
                if len(corrupted_list) == 0:
                    break
            if con_msg_type == (REQ+REJ) and con_data_length == 0 and con_frag_count == 1:
                print("Server response: RESENT datagram nr." + str(reply_frag_index) + " corrupted again")
    print(len(corrupted_list), "corrupted datagrams left")
    mysocket.close()
    file.close()
    pass


def become_client():
    try:
        mysocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        print("Client socket created")
    except socket.error:
        print("Failed to create client socket")
        exit()
    server_IP = input("Please enter the destination IP address: ")
    server_port = input("Please enter the destination port: ")
    server_port = 8484
    transfer = input("Do you wish to send text messages[1] or files[2]?")
    if(transfer == 1):
        send_msg(mysocket, server_IP, server_port)
    else:
        send_file(mysocket, server_IP, server_port)



role = input("Do you wish to be a receiver?[Y/n]")
if(role == "Y" or role == "y"):
    become_server()
else:
    become_client()

'''
try:
    mysocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print("Client socket created")
except socket.error:
    print("Failed to create socket")
    exit()
read_file = "/home/nicolas/Documents/FIIT/PKS/3_Rel_Prez_UDP.pdf"
server_address = ('localhost', 8484)
address_size = sys.getsizeof(server_address)  # print(str(sys.getsizeof(server_address)))
header_size = struct.calcsize('BHHHH')
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
    if frag_index != 78:
        crcstr = encode_data(data_as_string[2:], key)
        crc = int(crcstr[-(len(key) - 1):], 2)
    else:
        data = data[2:]
        print("Intentionally sending smaller datagram ", len(data))
        crcstr = encode_data(data_as_string[4:], key)
        crc = int(crcstr[-(len(key) - 1):], 2)
    header = struct.pack('BHHHH', msg_type, data_length, frag_count, frag_index, crc)
    mysocket.sendto(header + bytearray(data), server_address) # print("Datagram sent, awaiting response from server...")
    data_stream = mysocket.recvfrom(address_size + header_size)  # receives only header
    reply_data = data_stream[0]
    (reply_msg_type, reply_data_length, reply_frag_count, reply_frag_index, reply_crc) = struct.unpack('BHHHH',
                                                                                                       reply_data)
    notification = "Server response: "
    if reply_data_length == 1:
        notification += "datagram nr. " + str(frag_index) + " arrived successfully."
    else:
        print("Server response: CORRUPTED datagram", reply_frag_index)
        corrupted_list.append(reply_frag_index)
        notification += "datagram nr. " + str(reply_frag_index) + " arrived corrupted and will be resent after delivery of other datagrams."
    print(notification)
    contents = contents[frag_size:]
    frag_index += 1
print("All datagrams sent, informing server...", corrupted_list)
if msg_type == 1:
    info_header = struct.pack('BHHHH', 1, 1, 1, 1, 0)
    mysocket.sendto(info_header, server_address)

data_stream = mysocket.recvfrom(address_size + header_size)
reply_data = data_stream[0]
(reply_msg_type, reply_data_length, reply_frag_count, reply_frag_index, reply_crc) = struct.unpack('BHHHH', reply_data)
if (reply_msg_type, reply_data_length, reply_frag_count, reply_frag_index) == (5, 0, 0, 0):
    print("Server response: All datagrams received successfully")
if (reply_msg_type, reply_data_length, reply_frag_count, reply_frag_index) == (5, 1, 1, 1):
    print("Server response: Corrupted datagrams detected, server is requesting them to be resent.")
    while len(corrupted_list) > 0:
        # mysocket.settimeout(3.0)
        data_stream = mysocket.recvfrom(address_size + header_size)
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

        data_stream = mysocket.recvfrom(address_size + header_size)
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
'''