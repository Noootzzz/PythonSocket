######################################################################################
# server.py
######################################################################################
import socket
import threading
import os
import json

SERVER = socket.gethostbyname(socket.gethostname())
PORT = 5000
ADDR = (SERVER,PORT)
FORMAT = 'utf-8'
DISCONNECT_MESSAGE = "/quit"
USER_DATA_FILE_NAME = "user_data.json"

json_lock = threading.Lock()

clients = []
clients_lock = threading.Lock()


def broadcast(message, exclude_conn=None):
    with clients_lock:
        for conn, _ in clients:
            if conn is exclude_conn:
                continue
            try:
                conn.sendall(message.encode(FORMAT))
            except OSError:
                pass


def save_user(addr, username):
    with json_lock:
        if os.path.exists(USER_DATA_FILE_NAME):
            with open(USER_DATA_FILE_NAME, "r", encoding=FORMAT) as file:
                users = json.load(file)
        else:
            users = []

        user_found = False
        for user in users:
            if user["username"] == username:
                user["ip"] = addr[0]
                user["port"] = addr[1]
                user_found = True
                break
        if not user_found:
            users.append({
                "ip": addr[0],
                "port": addr[1],
                "username": username,
            })

        with open(USER_DATA_FILE_NAME, "w", encoding=FORMAT) as file:
            json.dump(users, file, indent=4, ensure_ascii=False)


def handle_client(conn, addr):
    print(f"[SERVER] New connection : {addr}")
    username = None
    try:
        data = conn.recv(1024)
        if not data:
            return
        username = data.decode(FORMAT).strip()
        save_user(addr, username)

        with clients_lock:
            clients.append((conn, username))

        conn.sendall(f"Bienvenue {username} !".encode(FORMAT))
        broadcast(f"[SERVER] {username} a rejoint le chat.", exclude_conn=conn)
        print(f"[SERVER] {username} joined ({addr})")

        while True:
            data = conn.recv(1024)
            if not data:
                break
            msg = data.decode(FORMAT).strip()
            if not msg:
                continue

            if msg == DISCONNECT_MESSAGE:
                break

            print(f"[{username}] {msg}")
            broadcast(f"[{username}] {msg}", exclude_conn=conn)

    except ConnectionResetError:
        print(f"[SERVER] ERROR : {addr} disconnected.")
    finally:
        with clients_lock:
            clients[:] = [c for c in clients if c[0] is not conn]
        conn.close()
        if username:
            broadcast(f"[SERVER] {username} a quitté le chat.")
        print(f"[SERVER] {addr} disconnected.")


def start():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    print(f"[SERVER] Created server {ADDR}")
    server.bind(ADDR)
    server.listen()
    print(f"[SERVER] Listening for new users...")

    while True:
        (conn, addr) = server.accept()
        thread = threading.Thread(target=handle_client, args=(conn,addr))
        thread.start()
        print(f"[SERVER] Active connections : {threading.active_count()-1}")

start()
