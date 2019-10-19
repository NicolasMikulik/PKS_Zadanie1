import binascii
import math
import multiprocessing
import socket
import struct
import time


# Zdroj funkcii xor(a, b), mod2div(divident, divisor) a decode_data(data, key) pre CRC:
# https://www.geeksforgeeks.org/cyclic-redundancy-check-python/
# Princip komunikacie servera a klienta:
# https://www.binarytides.com/programming-udp-sockets-in-python/?fbclid=IwAR2-JPM5O9EhroW-5WsBSzu-53NFYfqN54WqKIA8WcrJEWKmmX8gZrBo-4Y
# UDP s umiestnovanim datagramov do pola podla indexu datagramu:
# https://stackoverflow.com/questions/40325616/sending-file-over-udp-divided-into-fragments?noredirect=1&lq=1
# Kniznica pouzita pre crc16; polynom x^16+x^12+x^5+1, decimalna hodnota=69665, hexad. hodnota=11021
# https://docs.python.org/3/library/binascii.html
# Najmensia povolena velkost dat v 1 datagrame je 3B

SYN = 1
ACK = 2
REJ = 4
FIN = 8
MSG = 16
FIL = 32
REQ = 64
KAL = 128
UDP_HEAD = 8
IP_HEAD = 20


def keepalive(socket_info):
    mysocket = socket_info[0]
    server_address = socket_info[1]
    while True:
        time.sleep(5.0)
        kal_header = struct.pack('BHHHH', KAL, 0, 0, 0, 0)
        mysocket.sendto(kal_header, server_address)


def hold_session_recv(socket_info):
    mysocket = socket_info[0]
    server_address = socket_info[1]
    header_size = struct.calcsize('BHHHH')
    waiting = 3
    while True:
        try:
            mysocket.settimeout(25.0)
            info = mysocket.recvfrom(header_size + UDP_HEAD)
            (kal, length, count, index, crc) = struct.unpack('BHHHH', info[0])
            if kal == KAL:
                print("Client is maintaining the session, server is responding")
                info_header = struct.pack('BHHHH', (KAL + ACK), 0, 0, 0, 0)
                mysocket.sendto(info_header, server_address)
            if kal == FIN or kal == (FIN + ACK):
                print("Client is closing the session, server is acknowledging.")
                info_header = struct.pack('BHHHH', (FIN + ACK), 0, 0, 0, 0)
                mysocket.sendto(info_header, server_address)
                mysocket.settimeout(None)
                break
            mysocket.settimeout(None)
        except socket.timeout:
            waiting -= 1
            if waiting == 0:
                print("Client stopped responding")
                info_header = struct.pack('BHHHH', FIN, 0, 0, 0, 0)
                mysocket.sendto(info_header, server_address)
                break
            print("No reply from client received.")
    print("End of keepalive.")


def maintain_session_recv(socket_info):
    mysocket = socket_info[0]
    server_address = socket_info[1]
    header_size = struct.calcsize('BHHHH')
    send_p = multiprocessing.Process(target=keepalive, args=(socket_info,))
    send_p.start()
    waiting = 3
    while True:
        try:
            mysocket.settimeout(25.0)
            info = mysocket.recvfrom(header_size + UDP_HEAD)
            (kal, length, count, index, crc) = struct.unpack('BHHHH', info[0])
            if kal == (KAL + ACK):
                print("Server is maintaining the session")
            if kal == FIN or kal == (FIN + ACK):
                print("Server is closing the session, client acknowledges.")
                info_header = struct.pack('BHHHH', (FIN+ACK), 0, 0, 0, 0)
                mysocket.sendto(info_header, server_address)
                send_p.terminate()
                mysocket.settimeout(None)
                break
            mysocket.settimeout(None)
        except socket.timeout:
            waiting -= 1
            if waiting == 0:
                print("Server stopped responding, client is closing the session.")
                info_header = struct.pack('BHHHH', FIN, 0, 0, 0, 0)
                mysocket.sendto(info_header, server_address)
                break
            print("No reply from server received.")
    print("End of keepalive.")


def receive_msg(mysocket, frag_size, client_address):
    header_size = struct.calcsize('BHHHH')
    info_header = struct.pack('BHHHH', (MSG + ACK), frag_size, 0, 0, 0)
    mysocket.sendto(info_header, client_address)
    print("Client set fragment size to: " + str(frag_size))
    history = list()
    contact = 1
    receiving = 1
    sending = 0
    while contact:
        received_frag = 0
        received_list = list()
        corrupted_list = list()
        while receiving:
            while True:
                try:
                    mysocket.settimeout(7.0)
                    data_stream = mysocket.recvfrom(frag_size + header_size + UDP_HEAD)
                    data = data_stream[0]
                    kal, length, count, index, crc = struct.unpack('BHHHH', data[:header_size])
                    if kal == KAL:
                        print("Client is typing.")
                        continue
                    if kal != KAL:
                        print("Client is sending a message.")
                    mysocket.settimeout(None)
                    break
                except socket.timeout:
                    print("Waiting for message from client.")
            '''data_stream = mysocket.recvfrom(frag_size + header_size + UDP_HEAD)
            data = data_stream[0]  # addr = data_stream[1]'''
            header = data[:header_size]
            received_list.append(b'')  # received_file += data[header_size:]
            (msg_type, data_length, frag_count, frag_index, crc) = struct.unpack('BHHHH', header)

            if (msg_type, data_length, frag_count, frag_index, crc) == ((MSG+FIN), 0, 0, 0, 0):
                print("Client will not be sending more text messages")
                info_header = struct.pack('BHHHH',(MSG+FIN), 1, 1, 1, 0)
                mysocket.sendto(info_header, client_address)
                contact = 0
                receiving = 0
                continue
            crc_check = binascii.crc_hqx(data[header_size:], 0)
            if crc_check == crc:
                print("Datagram nr. " + str(frag_index) + ": correct crc")
                reply_header = struct.pack('BHHHH', (MSG + ACK), 1, 1, frag_index, 0)
                mysocket.sendto(reply_header, client_address)
                received_list[frag_index] = data[header_size:]
            else:
                print("---Datagram nr. " + str(frag_index) + ": INCORRECT crc---")
                reply_header = struct.pack('BHHHH', (MSG + REJ), 0, 1, frag_index, 0)
                corrupted_list.append(frag_index)
                mysocket.sendto(reply_header, client_address)
            received_frag += 1
            if received_frag == frag_count:
                print("Index of last received datagram was equal to number of all datagrams.")
                break
        if receiving == 1:
            data_stream = mysocket.recvfrom(header_size + UDP_HEAD)
            (msg_type, data_length, frag_count, frag_index, info_crc) = struct.unpack('BHHHH', data_stream[0])
            if ((MSG + ACK), 1, 1, 1) == (msg_type, data_length, frag_count, frag_index):
                print("Client confirmed it has sent all datagrams")
            print("Number of corrupted datagrams ", len(corrupted_list), corrupted_list)
            if len(corrupted_list) != 0:
                info_header = struct.pack('BHHHH', (MSG + REJ + FIN), 1, 1, 1, 0)
                mysocket.sendto(info_header, client_address)
                print((MSG + REJ + FIN), "1, 1, 1, 0")
            if len(corrupted_list) != 0:
                while len(corrupted_list) > 0:
                    requested_index = corrupted_list[0]
                    print("Requesting datagram nr.", requested_index)
                    reply_header = struct.pack('BHHHH', REQ, 0, 1, requested_index, 0)
                    mysocket.sendto(reply_header, client_address)

                    data_stream = mysocket.recvfrom(frag_size + header_size + UDP_HEAD)
                    data = data_stream[0]
                    header = data[:header_size]
                    (reply_msg_type, reply_data_length, reply_frag_count, reply_frag_index, reply_crc) = struct.unpack('BHHHH',
                                                                                                                       header)
                    crc_check = binascii.crc_hqx(data[header_size:], 0)
                    if crc_check == reply_crc:
                        print("Received requested datagram nr.", reply_frag_index, "from client, correct CRC")
                        received_list[reply_frag_index] = data[header_size:]
                        corrupted_list.pop(0)
                        reply_header = struct.pack('BHHHH', (REQ + ACK), 1, 1, 1, 0)
                        mysocket.sendto(reply_header, client_address)
                    else:
                        print("---Received requested datagram nr.", reply_frag_index, "INCORRECT CRC, requesting again...---")
                        reply_header = struct.pack('BHHHH', (REQ + REJ), 0, 1, reply_frag_index, 0)
                        mysocket.sendto(reply_header, client_address)
            else:
                reply_header = struct.pack('BHHHH', (MSG + ACK + FIN), 0, 0, 0, 0)
                mysocket.sendto(reply_header, client_address)
            received_msg = b''.join(received_list)
            message_entry = "Client: " + b''.join(received_list).decode()
            history.append(message_entry)
            print("Client:", received_msg.decode())

            print("Please enter messages longer than 2 characters (3 characters min.).")
            receiving = 0
            sending = 1
        frag_index = 0
        message = ""
        if sending:
            info = (mysocket, client_address)
            p = multiprocessing.Process(target=keepalive, args=(info,))
            p.start()
            while (len(message) < 3):
                message = input("Message to be sent [type 'exit' to stop]: ")
            p.terminate()
            if message == "exit":
                info_header = struct.pack('BHHHH', (MSG + FIN), 0, 0, 0, 0)
                mysocket.sendto(info_header, client_address)
                print("Client was informed about finishing the sending of messages.")
                server_reply = mysocket.recvfrom(header_size + UDP_HEAD)
                (reply_msg_type, reply_data_length, reply_frag_count, reply_frag_index, reply_crc) = struct.unpack(
                    'BHHHH',
                    server_reply[0])
                if (reply_msg_type, reply_data_length, reply_frag_count, reply_frag_index) == ((MSG + FIN), 1, 1, 1):
                    print("Client response: Confirming the end of messages.")
                else:
                    print("Client does not confirm the end of messages.")
                contact = 0
                continue
            if contact == 1:
                message_entry = "Server: " + message
                history.append(message_entry)
                contents = str.encode(message)
                read_contents = bytearray()
                read_contents.extend(contents[0:])
                msg_size = len(contents)
                frag_count = math.floor(msg_size / int(frag_size))
                if frag_count < 1:
                    frag_count = 1
                print("Message of size " + str(msg_size) + " is being sent in " + str(frag_count) + " datagrams")
                corrupted_list = list()
                while contents:
                    data = bytearray()
                    if len(contents) - 2*frag_size < 0:
                        data.extend(contents)
                        contents = contents[frag_size:]
                    else:
                        data.extend(contents[:frag_size])
                    data_length = len(data)
                    if frag_index != 2:
                        crc = binascii.crc_hqx(data, 0)
                    else:
                        data = data[2:]
                        print("Intentionally sending smaller datagram ", len(data))
                        crc = binascii.crc_hqx(data[1:], 0)
                    header = struct.pack('BHHHH', MSG, data_length, frag_count, frag_index, crc)
                    mysocket.sendto(header + bytearray(data),
                                    client_address)  # print("Datagram sent, awaiting response from server...")
                    data_stream = mysocket.recvfrom(header_size + UDP_HEAD)  # receives only header
                    reply_data = data_stream[0]
                    (reply_msg_type, reply_data_length, reply_frag_count, reply_frag_index, reply_crc) = struct.unpack(
                        'BHHHH',
                        reply_data)
                    notification = "Client response: "
                    if reply_msg_type == (MSG + ACK):
                        notification += "datagram nr. " + str(reply_frag_index) + " arrived successfully."
                    if reply_msg_type == (MSG + REJ):
                        print("---Client response: CORRUPTED datagram", str(reply_frag_index) + "---")
                        corrupted_list.append(reply_frag_index)
                        notification += "datagram nr. " + str(
                            reply_frag_index)+" arrived corrupted and will be resent after delivery of other datagrams."
                    print(notification)
                    contents = contents[frag_size:]
                    frag_index += 1
                print("All datagrams sent, informing client...", corrupted_list)
                info_header = struct.pack('BHHHH', MSG + ACK, 1, 1, 1, 0)
                mysocket.sendto(info_header, client_address)

                data_stream = mysocket.recvfrom(header_size + UDP_HEAD)
                reply_data = data_stream[0]
                (reply_msg_type, reply_data_length, reply_frag_count, reply_frag_index, reply_crc) = struct.unpack(
                    'BHHHH',
                    reply_data)
                print(reply_msg_type, reply_data_length, reply_frag_count, reply_frag_index, reply_crc)
                if (reply_msg_type, reply_data_length, reply_frag_count, reply_frag_index) == (
                (MSG + ACK + FIN), 0, 0, 0):
                    print("Client response: All datagrams received successfully")
                if (reply_msg_type, reply_data_length, reply_frag_count, reply_frag_index) == (
                (MSG + REJ + FIN), 1, 1, 1):
                    print("Client response: Corrupted datagrams detected, server is requesting them to be resent.")
                    while len(corrupted_list) > 0:
                        # mysocket.settimeout(3.0)
                        data_stream = mysocket.recvfrom(header_size + UDP_HEAD)
                        reply_data = data_stream[0]
                        (reply_msg_type, reply_data_length, reply_frag_count, reply_frag_index,
                         reply_crc) = struct.unpack('BHHHH',
                                                    reply_data)
                        print("Server: Resending requested datagram nr.", reply_frag_index)
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
                        mysocket.sendto(header + bytearray(data), client_address)

                        data_stream = mysocket.recvfrom(header_size + UDP_HEAD)
                        con_data = data_stream[0]
                        (con_msg_type, con_data_length, con_frag_count, con_frag_index, con_crc) = struct.unpack(
                            'BHHHH', con_data)
                        if (con_msg_type, con_data_length, con_frag_count, con_frag_index) == ((REQ + ACK), 1, 1, 1):
                            print("Client response: RESENT datagram nr." + str(
                                reply_frag_index) + " received successfully")
                            corrupted_list.remove(reply_frag_index)
                            if len(corrupted_list) == 0:
                                break
                        if con_msg_type == (REQ + REJ) and con_data_length == 0 and con_frag_count == 1:
                            print("Client response: RESENT datagram nr." + str(reply_frag_index) + " corrupted again")
                print(len(corrupted_list), "corrupted datagrams left, expecting reply from client")
                receiving = 1
                sending = 0
    info = (mysocket, client_address)
    p = multiprocessing.Process(target=hold_session_recv, args=(info,))
    p.start()
    while True:
        if (p.is_alive() == False):
            print("Keepalive session not present anymore.")
        answer = input("Press [1] to view message history, [2] to end keepalive session.")
        if answer == "1":
            print(history, "\n")
        if answer == "2":
            p.terminate()  # print("Process was terminated")
            info_header = struct.pack('BHHHH', FIN, 0, 0, 0, 0)
            mysocket.sendto(info_header, client_address)
            break
    info_header = struct.pack('BHHHH', (FIN+ACK), 0, 0, 0, 0)
    mysocket.sendto(info_header, client_address)
    print("Closing server socket.")
    mysocket.close()
    pass


def receive_fil(mysocket, frag_size, client_address):
    header_size = struct.calcsize('BHHHH')
    info_header = struct.pack('BHHHH', (FIL + ACK), frag_size, 0, 0, 0)
    mysocket.sendto(info_header, client_address)
    received_file = bytearray()
    print("Client set fragment size to: " + str(frag_size))
    received_frag = 0
    received_list = list()
    corrupted_list = list()
    while True:
        mysocket.settimeout(5.0)
        data_stream = mysocket.recvfrom(frag_size + header_size + UDP_HEAD)
        mysocket.settimeout(None)
        data = data_stream[0]  # addr = data_stream[1]
        header = data[:header_size]
        received_list.append(b'')  # received_file += data[header_size:]
        (msg_type, data_length, frag_count, frag_index, crc) = struct.unpack('BHHHH', header)

        crc_check = binascii.crc_hqx(data[header_size:],0)
        if crc_check == crc:
            print("Datagram nr. " + str(frag_index) + ": correct crc")
            reply_header = struct.pack('BHHHH', (FIL+ACK), 1, 1, frag_index, 0)
            mysocket.sendto(reply_header, client_address)
            received_list[frag_index] = data[header_size:]
        else:
            print("---Datagram nr. " + str(frag_index) + ": INCORRECT crc---")
            reply_header = struct.pack('BHHHH', (FIL+REJ), 0, 1, frag_index, 0)
            corrupted_list.append(frag_index)
            mysocket.sendto(reply_header, client_address)
        received_frag += 1
        if received_frag == frag_count:
            print("Index of last received datagram was equal to number of all datagrams.")
            break
    data_stream = mysocket.recvfrom(header_size + UDP_HEAD)
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

            data_stream = mysocket.recvfrom(frag_size + header_size + UDP_HEAD)
            data = data_stream[0]
            header = data[:header_size]
            (reply_msg_type, reply_data_length, reply_frag_count, reply_frag_index, reply_crc) = struct.unpack('BHHHH',
                                                                                                               header)
            crc_check = binascii.crc_hqx(data[header_size:],0)
            if crc_check == reply_crc:
                print("Received requested datagram nr.", reply_frag_index, "from client, correct CRC")
                received_list[reply_frag_index] = data[header_size:]
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


def send_msg(mysocket, server_IP, server_port):
    server_address = ('127.0.0.1', 60500)
    header_size = struct.calcsize('BHHHH')
    history = list()
    frag_size = int(input("Please enter maximum size of a datagram in bytes: "))
    if frag_size > (1500 - IP_HEAD - UDP_HEAD - header_size):
        frag_size = 1500 - IP_HEAD - UDP_HEAD - header_size
        print("Entered size of datagram was too large, size was set to the value of", frag_size, "bytes.")
    if frag_size < 3:
        frag_size = 3
        print("Entered size of datagram was too small, size was set to the value of", frag_size, "bytes.")
    info_header = struct.pack('BHHHH', (MSG + SYN), frag_size, 0, 0, 0)
    mysocket.sendto(info_header, server_address)
    print("Server was informed about sending text messages and about datagram size.")
    server_reply = mysocket.recvfrom(header_size + UDP_HEAD)
    (reply_msg_type, reply_data_length, reply_frag_count, reply_frag_index, reply_crc) = struct.unpack('BHHHH',
                                                                                                       server_reply[0])
    if reply_msg_type == (MSG + ACK) and reply_data_length == frag_size:
        print("Server response: Prepared to receive text messages.")
    contact = 1
    sending = 1
    receiving = 0
    print("Please enter messages longer than 2 characters (3 characters min.).")
    while contact:
        frag_index = 0
        message = ""
        if sending:
            info = (mysocket, server_address)
            p = multiprocessing.Process(target=keepalive, args=(info,))
            p.start()
            while(len(message) < 3):
                message = input("Message to be sent [type 'exit' to stop]: ")
            p.terminate()
            if message == "exit":
                info_header = struct.pack('BHHHH', (MSG + FIN), 0, 0, 0, 0)
                mysocket.sendto(info_header, server_address)
                print("Server was informed about finishing the sending of messages.")
                server_reply = mysocket.recvfrom(header_size + UDP_HEAD)
                (reply_msg_type, reply_data_length, reply_frag_count, reply_frag_index, reply_crc) = struct.unpack('BHHHH',
                                                                                                                   server_reply[0])
                if (reply_msg_type, reply_data_length, reply_frag_count, reply_frag_index) == ((MSG+FIN), 1, 1, 1):
                    print("Server response: Confirming the end of messages.")
                else:
                    print("Server does not confirm the end of messages.")
                contact = 0
                continue
            if contact == 1:
                message_entry = "Client: " + message
                history.append(message_entry)
                contents = str.encode(message)
                read_contents = bytearray()
                read_contents.extend(contents[0:])
                msg_size = len(contents)
                frag_count = math.floor(msg_size / int(frag_size))
                if frag_count < 1:
                    frag_count = 1
                print("Message of size " + str(msg_size) + " is being sent in " + str(frag_count) + " datagrams")
                corrupted_list = list()
                while contents:
                    data = bytearray()
                    if len(contents) - 2*frag_size < 0:
                        data.extend(contents)
                        contents = contents[frag_size:]
                    else:
                        data.extend(contents[:frag_size])
                    data_length = len(data)
                    if frag_index != 2:
                        crc = binascii.crc_hqx(data, 0)
                    else:
                        data = data[2:]
                        print("Intentionally sending smaller datagram ", len(data))
                        crc = binascii.crc_hqx(data[1:], 0)
                    header = struct.pack('BHHHH', MSG, data_length, frag_count, frag_index, crc)
                    mysocket.sendto(header + bytearray(data),
                                    server_address)  # print("Datagram sent, awaiting response from server...")
                    data_stream = mysocket.recvfrom(header_size + UDP_HEAD)  # receives only header
                    reply_data = data_stream[0]
                    (reply_msg_type, reply_data_length, reply_frag_count, reply_frag_index, reply_crc) = struct.unpack('BHHHH',
                                                                                                                       reply_data)
                    notification = "Server response: "
                    if reply_msg_type == (MSG + ACK):
                        notification += "datagram nr. " + str(reply_frag_index) + " arrived successfully."
                    if reply_msg_type == (MSG + REJ):
                        print("---Server response: CORRUPTED datagram", str(reply_frag_index) + "---")
                        corrupted_list.append(reply_frag_index)
                        notification += "datagram nr. " + str(
                            reply_frag_index) + " arrived corrupted and will be resent after delivery of other datagrams."
                    print(notification)
                    contents = contents[frag_size:]
                    frag_index += 1
                print("All datagrams sent, informing server...", corrupted_list)
                info_header = struct.pack('BHHHH', MSG + ACK, 1, 1, 1, 0)
                mysocket.sendto(info_header, server_address)

                data_stream = mysocket.recvfrom(header_size + UDP_HEAD)
                reply_data = data_stream[0]
                (reply_msg_type, reply_data_length, reply_frag_count, reply_frag_index, reply_crc) = struct.unpack('BHHHH',
                                                                                                                   reply_data)
                print(reply_msg_type, reply_data_length, reply_frag_count, reply_frag_index, reply_crc)
                if (reply_msg_type, reply_data_length, reply_frag_count, reply_frag_index) == ((MSG + ACK + FIN), 0, 0, 0):
                    print("Server response: All datagrams received successfully")
                if (reply_msg_type, reply_data_length, reply_frag_count, reply_frag_index) == ((MSG + REJ + FIN), 1, 1, 1):
                    print("Server response: Corrupted datagrams detected, server is requesting them to be resent.")
                    while len(corrupted_list) > 0:
                        # mysocket.settimeout(3.0)
                        data_stream = mysocket.recvfrom(header_size + UDP_HEAD)
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

                        data_stream = mysocket.recvfrom(header_size + UDP_HEAD)
                        con_data = data_stream[0]
                        (con_msg_type, con_data_length, con_frag_count, con_frag_index, con_crc) = struct.unpack('BHHHH', con_data)
                        if (con_msg_type, con_data_length, con_frag_count, con_frag_index) == ((REQ + ACK), 1, 1, 1):
                            print("Server response: RESENT datagram nr." + str(reply_frag_index) + " received successfully")
                            corrupted_list.remove(reply_frag_index)
                            if len(corrupted_list) == 0:
                                break
                        if con_msg_type == (REQ + REJ) and con_data_length == 0 and con_frag_count == 1:
                            print("Server response: RESENT datagram nr." + str(reply_frag_index) + " corrupted again")
                print(len(corrupted_list), "corrupted datagrams left, expecting reply from server")
                receiving = 1
                sending = 0
                received_frag = 0
                received_list = list()
                corrupted_list = list()
                while receiving:
                    while True:
                        try:
                            mysocket.settimeout(7.0)
                            data_stream = mysocket.recvfrom(frag_size + header_size + UDP_HEAD)
                            data = data_stream[0]
                            kal, length, count, index, crc = struct.unpack('BHHHH', data[:header_size])
                            if kal == KAL:
                                print("Client is typing.")
                                continue
                            if kal != KAL:
                                print("Client is sending a message.")
                            mysocket.settimeout(None)
                            break
                        except socket.timeout:
                            print("Waiting for message from client.")
                    '''data_stream = mysocket.recvfrom(frag_size + header_size + UDP_HEAD)
                    data = data_stream[0]  # addr = data_stream[1]'''
                    header = data[:header_size]
                    received_list.append(b'')  # received_file += data[header_size:]
                    (msg_type, data_length, frag_count, frag_index, crc) = struct.unpack('BHHHH', header)

                    if (msg_type, data_length, frag_count, frag_index, crc) == ((MSG + FIN), 0, 0, 0, 0):
                        print("Server will not be sending more text messages")
                        info_header = struct.pack('BHHHH', (MSG + FIN), 1, 1, 1, 0)
                        mysocket.sendto(info_header, server_address)
                        contact = 0
                        receiving = 0
                        continue
                    crc_check = binascii.crc_hqx(data[header_size:], 0)
                    if crc_check == crc:
                        print("Datagram nr. " + str(frag_index) + ": correct crc")
                        reply_header = struct.pack('BHHHH', (MSG + ACK), 1, 1, frag_index, 0)
                        mysocket.sendto(reply_header, server_address)
                        received_list[frag_index] = data[header_size:]
                    else:
                        print("---Datagram nr. " + str(frag_index) + ": INCORRECT crc---")
                        reply_header = struct.pack('BHHHH', (MSG + REJ), 0, 1, frag_index, 0)
                        corrupted_list.append(frag_index)
                        mysocket.sendto(reply_header, server_address)
                    received_frag += 1
                    if received_frag == frag_count:
                        print("Index of last received datagram was equal to number of all datagrams.")
                        break
                if receiving == 1:
                    data_stream = mysocket.recvfrom(header_size + UDP_HEAD)
                    (msg_type, data_length, frag_count, frag_index, info_crc) = struct.unpack('BHHHH', data_stream[0])
                    if ((MSG + ACK), 1, 1, 1) == (msg_type, data_length, frag_count, frag_index):
                        print("Server confirmed it has sent all datagrams")
                    print("Number of corrupted datagrams ", len(corrupted_list), corrupted_list)
                    if len(corrupted_list) != 0:
                        info_header = struct.pack('BHHHH', (MSG + REJ + FIN), 1, 1, 1, 0)
                        mysocket.sendto(info_header, server_address)
                        print((MSG + REJ + FIN), "1, 1, 1, 0")
                    if len(corrupted_list) != 0:
                        while len(corrupted_list) > 0:
                            requested_index = corrupted_list[0]
                            print("Requesting datagram nr.", requested_index)
                            reply_header = struct.pack('BHHHH', REQ, 0, 1, requested_index, 0)
                            mysocket.sendto(reply_header, server_address)

                            data_stream = mysocket.recvfrom(frag_size + header_size + UDP_HEAD)
                            data = data_stream[0]
                            header = data[:header_size]
                            (reply_msg_type, reply_data_length, reply_frag_count, reply_frag_index,
                             reply_crc) = struct.unpack('BHHHH',
                                                        header)
                            crc_check = binascii.crc_hqx(data[header_size:], 0)
                            if crc_check == reply_crc:
                                print("Received requested datagram nr.", reply_frag_index, "from server, correct CRC")
                                received_list[reply_frag_index] = data[header_size:]
                                corrupted_list.pop(0)
                                reply_header = struct.pack('BHHHH', (REQ + ACK), 1, 1, 1, 0)
                                mysocket.sendto(reply_header, server_address)
                            else:
                                print("---Received requested datagram nr.", reply_frag_index,
                                      "INCORRECT CRC, requesting again...---")
                                reply_header = struct.pack('BHHHH', (REQ + REJ), 0, 1, reply_frag_index, 0)
                                mysocket.sendto(reply_header, server_address)
                    else:
                        reply_header = struct.pack('BHHHH', (MSG + ACK + FIN), 0, 0, 0, 0)
                        mysocket.sendto(reply_header, server_address)
                    received_msg = b''.join(received_list)
                    message_entry = "Server: "+b''.join(received_list).decode()
                    history.append(message_entry)
                    print("Server:",received_msg.decode())
                    receiving = 0
                    sending = 1
    print("Maintaining session...")
    info = (mysocket, server_address)
    p = multiprocessing.Process(target=maintain_session_recv, args=(info,))
    p.start()
    while True:
        answer = input("Press [1] to view message history, [2] to end keepalive session.")
        if answer == "1":
            print(history, "\n")
        if answer == "2":
            p.terminate()  # print("Process was terminated")
            info_header = struct.pack('BHHHH', FIN, 0, 0, 0, 0)
            mysocket.sendto(info_header, server_address)
            break

    print("Closing client socket")
    mysocket.close()
    pass


def send_file(mysocket, server_IP, server_port):
    server_address = ('127.0.0.1', 60500)
    header_size = struct.calcsize('BHHHH')
    frag_size = int(input("Please enter maximum size of a datagram in bytes: "))
    if frag_size > (1500 - IP_HEAD - UDP_HEAD - header_size):
        frag_size = 1500 - IP_HEAD - UDP_HEAD - header_size
        print("Entered size of datagram was too large, size was set to the value of", frag_size, "bytes.")
    if frag_size < 3:
        frag_size = 3
        print("Entered size of datagram was too small, size was set to the value of", frag_size, "bytes.")
    info_header = struct.pack('BHHHH', (FIL+SYN), frag_size, 0, 0, 0)
    mysocket.sendto(info_header, server_address)
    print("Server was informed about sending a file and about datagram size.")
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
    server_port = 60500
    transfer = input("Do you wish to send text messages[1] or files[2]?")
    if transfer == "1":
        send_msg(mysocket, server_IP, server_port)
    else:
        send_file(mysocket, server_IP, server_port)


def become_server():
    try:
        mysocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        print("Server socket created")
    except socket.error:
        print("Failed to create server socket")
        exit()
    port = input("Please enter the number of port on which you want to be receiving data: ")
    port = 60500
    server_address = ('localhost', port)
    try:  # Bind the socket to the port
        mysocket.bind(server_address)
        print('Starting up on {} port {}'.format(*server_address) + ". Waiting for fragment size.")
    except socket.error:
        print("Failed to bind socket")

    struct_header_size = struct.calcsize('BHHHH')
    init_info = mysocket.recvfrom(struct_header_size+UDP_HEAD)
    client_address = init_info[1]
    (init_type, frag_size, init_count, init_index, init_crc) = struct.unpack('BHHHH', init_info[0])
    if init_type == (MSG+SYN):
        receive_msg(mysocket, frag_size, client_address)
    if init_type == (FIL+SYN):
        receive_fil(mysocket, frag_size, client_address)


while True:
    role = input("Do you wish to be a receiver?[Y/n]")
    if(role == "Y" or role == "y"):
        become_server()
    if (role == "n" or role == "N"):
        become_client()
    if (role == "exit"):
        exit()

'''
try:
    mysocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print("Client socket created")
except socket.error:
    print("Failed to create socket")
    exit()
read_file = "/home/nicolas/Documents/FIIT/PKS/3_Rel_Prez_UDP.pdf"
server_address = ('localhost', 60500)
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