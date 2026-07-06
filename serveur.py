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

def handle_client(conn, addr):
    print(f"[SERVER] New connection : {addr}")
    first_message = True
    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break
            msg = data.decode(FORMAT)
            print(f"[{addr}] {msg}")

            if msg == DISCONNECT_MESSAGE:
                conn.sendall(f"[{addr}] Disconnect.".encode(FORMAT))
                break

            if first_message:
                user_data = {
                    "ip" : f"{addr[0]}",
                    "port" : f"{addr[1]}",
                    "username" : f"{msg}"
                }

                with json_lock:
                    if os.path.exists(USER_DATA_FILE_NAME):
                        with open(USER_DATA_FILE_NAME, "r", encoding=FORMAT) as file:
                            users = json.load(file)
                    else:
                        users = []
                    user_found = False

                    for user in users:
                        if user["username"] == msg:
                            user["ip"] = addr[0]
                            user["port"] = addr[1]
                            user_found = True
                            break
                    if not user_found:
                        users.append(user_data)

                    with open(USER_DATA_FILE_NAME, "w", encoding=FORMAT) as file:
                        json.dump(users, file, indent=4, ensure_ascii=False)

                username = msg
                first_message = False

            response = f"[{username}] : {msg}"
            conn.sendall(response.encode(FORMAT))
            print(f"[{username}] {msg}")

    except ConnectionResetError:
        print(f"[SERVER] ERROR : {addr} disconnected.")
    finally:
        conn.close()
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
