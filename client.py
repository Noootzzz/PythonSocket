######################################################################################
# client.py
######################################################################################

import socket
import threading
import os
import time

if os.name == "nt":
    os.system("")

SERVER = socket.gethostbyname(socket.gethostname())
PORT = 5000
ADDR = (SERVER,PORT)
FORMAT = 'utf-8'
DISCONNECT_MESSAGE = "/quit"

RESET = "\x1b[0m"
YELLOW = "\x1b[33m"
MAGENTA = "\x1b[35m"
CYAN = "\x1b[36m"
GREY = "\x1b[90m"

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect(ADDR)

running = True
ping_time = None


def colorize(text):
    if text.startswith("[SERVER]") or text.startswith("Bienvenue") or text.startswith("Déconnecté"):
        return YELLOW + text + RESET
    if text.startswith("[") and "[MP" in text:
        return MAGENTA + text + RESET
    return CYAN + text + RESET


def show(text):
    print(f"\r\x1b[K{text}\n> ", end="")


def receive():
    global running
    while running:
        try:
            data = client.recv(1024)
        except OSError:
            break
        if not data:
            break
        response = data.decode(FORMAT)
        if response == "/pong":
            latency = (time.time() - ping_time) * 1000
            show(f"{GREY}Ping : {latency:.0f} ms{RESET}")
        else:
            show(colorize(response))
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

    if message == "/clear":
        os.system("cls" if os.name == "nt" else "clear")
        continue

    if message == "/ping":
        ping_time = time.time()

    client.sendall(message.encode(FORMAT))

    if message == DISCONNECT_MESSAGE:
        running = False
        break

client.close()
print("Déconnecté.")
