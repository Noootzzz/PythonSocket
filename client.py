######################################################################################
# client.py
######################################################################################

import socket
SERVER = socket.gethostbyname(socket.gethostname())
PORT = 5000
ADDR = (SERVER,PORT)
FORMAT = 'utf-8'
DISCONNECT_MESSAGE = "/quit"

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

client.connect(ADDR)
connected = True
first_message = True
while connected:
    if first_message:
        message = input("> Enter your name : ")
        first_message = False
    else:
        message = input("> ")
    
    if not message:
        continue
    
    client.sendall(message.encode(FORMAT))
    data = client.recv(1024)
    response = data.decode(FORMAT)

    print(f"Réponse du serveur : {response}")
    if message == DISCONNECT_MESSAGE:
        break