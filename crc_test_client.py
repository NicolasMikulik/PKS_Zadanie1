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

try:
    mysocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print("Client socket created")
except socket.error:
    print("Failed to create socket")
    exit()

server_address = ('localhost', 8484)
# Send data to server 'Hello world'
readfile = open('/home/nicolas/PycharmProjects/pks_zadanie1/romeo_copy.txt', 'rb');
data = readfile.read()
crc = binascii.crc32(data)
send_data = (binascii.crc32(data[:-15]))
print(binascii.crc32(data), type(crc), send_data, type(send_data))
print(crc == send_data)
'''no_received_reply = 1
while no_received_reply:
    try:
        print("Sending a message to server...")
        mysocket.sendto("This is a message from client".encode(), server_address)
        mysocket.settimeout(7.0)
        mysocket.recvfrom(1024)
        break
    except socket.timeout:
        no_received_reply = 1'''
# close the connection
s.close()
