import socket

# OPEN
s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_UDP)

# customise options
s.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 0) #TODO since 0, we must write our own header? Can write in src/Objects/AHTP.py?

# receive 
while True:
    packet, addr = s.recvfrom(1024)
    print(f"Received packet from {addr}: {packet}")

s.close() 