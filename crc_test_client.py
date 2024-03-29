# Import socket module
import binascii
import socket


def xor(a, b):
    # initialize result
    result = []

    # Traverse all bits, if bits are
    # same, then XOR is 0, else 1
    for i in range(1, len(b)):
        if a[i] == b[i]:
            result.append('0')
        else:
            result.append('1')

    return ''.join(result)


# Performs Modulo-2 division
def mod2div(divident, divisor):
    # Number of bits to be XORed at a time.
    pick = len(divisor)

    # Slicing the divident to appropriate
    # length for particular step
    tmp = divident[0: pick]

    while pick < len(divident):

        if tmp[0] == '1':

            # replace the divident by the result
            # of XOR and pull 1 bit down
            tmp = xor(divisor, tmp) + divident[pick]

        else:  # If leftmost bit is '0'

            # If the leftmost bit of the dividend (or the
            # part used in each step) is 0, the step cannot
            # use the regular divisor; we need to use an
            # all-0s divisor.
            tmp = xor('0' * pick, tmp) + divident[pick]

            # increment pick to move further
        pick += 1

    # For the last n bits, we have to carry it out
    # normally as increased value of pick will cause
    # Index Out of Bounds.
    if tmp[0] == '1':
        tmp = xor(divisor, tmp)
    else:
        tmp = xor('0' * pick, tmp)

    checkword = tmp
    return checkword


# Function used at the sender side to encode
# data by appending remainder of modular division
# at the end of data.
def encodeData(data, key):
    l_key = len(key)

    # Appends n-1 zeroes at end of data
    appended_data = data + '0' * (l_key - 1)
    remainder = mod2div(appended_data, key)

    # Append remainder in the original data
    codeword = data + remainder
    return codeword

maxcrc = 0xffffffff

def inverse_crc(data):
    crc = binascii.crc32(data) & maxcrc


# Create a socket object
s = socket.socket()

import time, multiprocessing
def keepalive(socket_info, process):
    mysocket = socket_info[0]
    server_address = socket_info[1]
    while True:
        time.sleep(2.5)
        print("\nStatement", server_address)
        mysocket.sendto("Client: Maintaining session".encode(), ('localhost', 8484))
        data = mysocket.recvfrom(1024)[0].decode()
        print( data ,"\n")
        if data[0] == "S":
            print("Hello")
            process.terminate()


try:
    mysocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print("Client socket created")
except socket.error:
    print("Failed to create socket")
    exit()

server_address = ('localhost', 8484)
# Send data to server 'Hello world'
info = (mysocket, server_address)
readfile = open('/home/nicolas/PycharmProjects/pks_zadanie1/romeo_copy19.txt', 'rb')
data = readfile.read()
crc = binascii.crc32(data)
send_data = (binascii.crc32(data[:-15]))
print(binascii.crc32(data), type(crc), send_data, type(send_data))
print(crc == send_data)
no_received_reply = 1
p = multiprocessing.Process(target=keepalive, args=(info,))
p = multiprocessing.Process(target=keepalive, args=(info, p))
p.start()
while no_received_reply:
    answer = input("End?[y/n]")
    print(p.is_alive())
    if answer == "y":
        p.terminate()
        print("Process was terminated")
        break
    '''try:
        keeper = threading.Timer(10.0, keepalive).start()
        print("Sending a message to server...")
        mysocket.settimeout(15.0)
        data = mysocket.recvfrom(1024)
        print(data[0].decode(), "response")
        mysocket.settimeout(None)
    except socket.timeout:
        print("Server did not respond in time")
        no_received_reply = 1'''
# close the connection
print(p.is_alive())
s.close()