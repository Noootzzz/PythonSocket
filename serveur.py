######################################################################################
# server.py
######################################################################################
import socket
import threading
import os
import json
import datetime

SERVER = socket.gethostbyname(socket.gethostname())
PORT = 5000
ADDR = (SERVER,PORT)
FORMAT = 'utf-8'
DISCONNECT_MESSAGE = "/quit"
USER_DATA_FILE_NAME = "user_data.json"

json_lock = threading.Lock()

clients = {}
clients_lock = threading.Lock()


def broadcast(message, exclude_conn=None):
    with clients_lock:
        for conn in clients:
            if conn is exclude_conn:
                continue
            try:
                conn.sendall(message.encode(FORMAT))
            except OSError:
                pass


def find_conn_by_name(name):
    with clients_lock:
        for conn, user in clients.items():
            if user == name:
                return conn
    return None


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


def handle_command(conn, addr, username, msg):
    parts = msg.split()
    cmd = parts[0].lower()

    if cmd == "/time":
        now = datetime.datetime.now().strftime("%H:%M:%S")
        conn.sendall(f"[SERVER] Heure du serveur : {now}".encode(FORMAT))
        return True, None

    if cmd == "/ping":
        conn.sendall("/pong".encode(FORMAT))
        return True, None

    if cmd == "/rename":
        if len(parts) < 2:
            conn.sendall("[SERVER] Usage : /rename <nouveau_pseudo>".encode(FORMAT))
            return True, None
        new_name = parts[1]
        with clients_lock:
            if new_name in clients.values():
                conn.sendall("[SERVER] Ce pseudo est déjà pris.".encode(FORMAT))
                return True, None
            clients[conn] = new_name
        save_user(addr, new_name)
        conn.sendall(f"[SERVER] Tu es maintenant '{new_name}'.".encode(FORMAT))
        broadcast(f"[SERVER] {username} est maintenant {new_name}.", exclude_conn=conn)
        print(f"[SERVER] {username} -> {new_name}")
        return True, new_name

    if cmd == "/mp":
        cut = msg.split(maxsplit=2)
        if len(cut) < 3:
            conn.sendall("[SERVER] Usage : /mp <pseudo> <message>".encode(FORMAT))
            return True, None
        target_name = cut[1]
        private_msg = cut[2]
        target = find_conn_by_name(target_name)
        if target is None:
            conn.sendall(f"[SERVER] Utilisateur '{target_name}' introuvable.".encode(FORMAT))
            return True, None
        target.sendall(f"[MP de {username}] {private_msg}".encode(FORMAT))
        conn.sendall(f"[MP à {target_name}] {private_msg}".encode(FORMAT))
        return True, None

    return False, None


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
            clients[conn] = username

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

            if msg.startswith("/"):
                handled, new_name = handle_command(conn, addr, username, msg)
                if not handled:
                    conn.sendall(f"[SERVER] Commande inconnue : {msg}".encode(FORMAT))
                elif new_name:
                    username = new_name
                continue

            print(f"[{username}] {msg}")
            broadcast(f"[{username}] {msg}", exclude_conn=conn)

    except ConnectionResetError:
        print(f"[SERVER] ERROR : {addr} disconnected.")
    finally:
        with clients_lock:
            clients.pop(conn, None)
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
