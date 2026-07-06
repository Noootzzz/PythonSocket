######################################################################################
# client.py
######################################################################################

import socket
import threading

SERVER = socket.gethostbyname(socket.gethostname())
PORT = 5000
ADDR = (SERVER,PORT)
FORMAT = 'utf-8'
DISCONNECT_MESSAGE = "/quit"

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect(ADDR)

running = True


def receive():
    global running
    while running:
        try:
            data = client.recv(1024)
        except OSError:
            break
        if not data:
            break
        print(f"\r{data.decode(FORMAT)}\n> ", end="")
    running = False


name = input("> Enter your name : ")
client.sendall(name.encode(FORMAT))

thread = threading.Thread(target=receive, daemon=True)
thread.start()

while running:
    try:
        message = input("> ")
    except (EOFError, KeyboardInterrupt):
        message = DISCONNECT_MESSAGE

    if not message:
        continue

    client.sendall(message.encode(FORMAT))

    if message == DISCONNECT_MESSAGE:
        running = False
        break

client.close()
print("Déconnecté.")
