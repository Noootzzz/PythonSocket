######################################################################################
# server.py
######################################################################################
import socket
import threading
import os
import json
import datetime
import re
import time

SERVER = socket.gethostbyname(socket.gethostname())
PORT = 5000
ADDR = (SERVER,PORT)
FORMAT = 'utf-8'
DISCONNECT_MESSAGE = "/quit"
USER_DATA_FILE_NAME = "user_data.json"
TIMEOUT = 180

ROLES = {"user": 0, "moderateur": 1, "admin": 2}
DEFAULT_ROOM = "general"
MAX_MSG_LEN = 500
USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]{3,20}$")
CHECK_INTERVAL = min(5, TIMEOUT)
PASSIVE_COMMANDS = {"/online", "/rooms"}


def send(sock, text):
    try:
        sock.sendall((text + "\n").encode(FORMAT))
    except OSError:
        pass


def clean_text(text):
    return "".join(ch for ch in text if ch.isprintable())


def stamp():
    return datetime.datetime.now().strftime("%H:%M")


def valid_username(name):
    return bool(USERNAME_RE.match(name))

json_lock = threading.Lock()

clients = {}
clients_lock = threading.Lock()

rooms = {DEFAULT_ROOM}
rooms_lock = threading.Lock()


def broadcast(message, room=None, exclude_conn=None):
    with clients_lock:
        for conn, info in clients.items():
            if conn is exclude_conn:
                continue
            if room is not None and info["room"] != room:
                continue
            send(conn, message)


def prune_room(room):
    if room == DEFAULT_ROOM:
        return
    with clients_lock:
        still_used = any(info["room"] == room for info in clients.values())
    if not still_used:
        with rooms_lock:
            rooms.discard(room)


def find_conn_by_name(name):
    with clients_lock:
        for conn, info in clients.items():
            if info["username"] == name:
                return conn
    return None


def my_role(conn):
    with clients_lock:
        info = clients.get(conn)
        return info["role"] if info else "user"


def has_level(role, needed):
    return ROLES.get(role, 0) >= ROLES[needed]


def load_users():
    if not os.path.exists(USER_DATA_FILE_NAME):
        return []
    try:
        with open(USER_DATA_FILE_NAME, "r", encoding=FORMAT) as file:
            return json.load(file)
    except (json.JSONDecodeError, ValueError):
        return []


def save_users(users):
    with open(USER_DATA_FILE_NAME, "w", encoding=FORMAT) as file:
        json.dump(users, file, indent=4, ensure_ascii=False)


def register_user(addr, username):
    with json_lock:
        users = load_users()
        found = None
        for user in users:
            if user["username"] == username:
                found = user
                break
        if found is None:
            found = {"ip": addr[0], "port": addr[1], "username": username, "role": "user"}
            users.append(found)
        else:
            found["ip"] = addr[0]
            found["port"] = addr[1]
            found.setdefault("role", "user")

        if not any(u.get("role") == "admin" for u in users):
            found["role"] = "admin"

        save_users(users)
        return found["role"]


def set_role_in_file(username, role):
    with json_lock:
        users = load_users()
        for user in users:
            if user["username"] == username:
                user["role"] = role
                save_users(users)
                return True
        return False


def set_banned_in_file(username, value):
    with json_lock:
        users = load_users()
        for user in users:
            if user["username"] == username:
                user["banned"] = value
                save_users(users)
                return True
        return False


def is_banned(username):
    with json_lock:
        for user in load_users():
            if user["username"] == username and user.get("banned"):
                return True
    return False


def can_moderate(actor_conn, target_conn):
    return ROLES.get(my_role(actor_conn), 0) > ROLES.get(my_role(target_conn), 0)


def disconnect(target_conn, reason):
    send(target_conn, f"[SERVER] {reason}")
    try:
        target_conn.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass


def handle_command(conn, addr, username, msg):
    parts = msg.split()
    cmd = parts[0].lower()

    if cmd == "/time":
        now = datetime.datetime.now().strftime("%H:%M:%S")
        send(conn, f"[SERVER] Heure du serveur : {now}")
        return True, None

    if cmd == "/ping":
        send(conn, "/pong")
        return True, None

    if cmd == "/role":
        send(conn, f"[SERVER] Ton rôle : {my_role(conn)}.")
        return True, None

    if cmd == "/rename":
        if len(parts) < 2:
            send(conn, "[SERVER] Usage : /rename <nouveau_pseudo>")
            return True, None
        new_name = parts[1]
        if not valid_username(new_name):
            send(conn, "[SERVER] Pseudo invalide (3-20 caractères : lettres, chiffres, _ ou -).")
            return True, None
        with clients_lock:
            taken = any(info["username"] == new_name for info in clients.values())
        if taken:
            send(conn, "[SERVER] Ce pseudo est déjà pris.")
            return True, None
        current_role = my_role(conn)
        register_user(addr, new_name)
        set_role_in_file(new_name, current_role)
        with clients_lock:
            if conn in clients:
                clients[conn]["username"] = new_name
        send(conn, f"[SERVER] Tu es maintenant '{new_name}'.")
        broadcast(f"[SERVER] {username} est maintenant {new_name}.", exclude_conn=conn)
        print(f"[SERVER] {username} -> {new_name}")
        return True, new_name

    if cmd == "/mp":
        cut = msg.split(maxsplit=2)
        if len(cut) < 3:
            send(conn, "[SERVER] Usage : /mp <pseudo> <message>")
            return True, None
        target_name = cut[1]
        private_msg = cut[2]
        target = find_conn_by_name(target_name)
        if target is None:
            send(conn, f"[SERVER] Utilisateur '{target_name}' introuvable.")
            return True, None
        send(target, f"[{stamp()}] [MP de {username}] {private_msg}")
        send(conn, f"[{stamp()}] [MP à {target_name}] {private_msg}")
        return True, None

    if cmd in ("/setadmin", "/setmodo", "/remadmin", "/remmodo"):
        if not has_level(my_role(conn), "admin"):
            send(conn, "[SERVER] Commande réservée aux admins.")
            return True, None
        if len(parts) < 2:
            send(conn, f"[SERVER] Usage : {cmd} <pseudo>")
            return True, None
        target_name = parts[1]
        if cmd == "/setadmin":
            new_role = "admin"
        elif cmd == "/setmodo":
            new_role = "moderateur"
        else:
            new_role = "user"
        if not set_role_in_file(target_name, new_role):
            send(conn, f"[SERVER] Utilisateur '{target_name}' introuvable.")
            return True, None
        target = find_conn_by_name(target_name)
        if target is not None:
            with clients_lock:
                clients[target]["role"] = new_role
            send(target, f"[SERVER] Ton rôle est maintenant : {new_role}.")
        send(conn, f"[SERVER] {target_name} est maintenant {new_role}.")
        print(f"[SERVER] {username} a mis {target_name} en {new_role}")
        return True, None

    if cmd in ("/kick", "/mute", "/unmute"):
        if not has_level(my_role(conn), "moderateur"):
            send(conn, "[SERVER] Commande réservée aux modérateurs et admins.")
            return True, None
        if len(parts) < 2:
            send(conn, f"[SERVER] Usage : {cmd} <pseudo>")
            return True, None
        target_name = parts[1]
        target = find_conn_by_name(target_name)
        if target is None:
            send(conn, f"[SERVER] Utilisateur '{target_name}' introuvable.")
            return True, None
        if not can_moderate(conn, target):
            send(conn, "[SERVER] Tu ne peux pas modérer cet utilisateur.")
            return True, None

        if cmd == "/kick":
            disconnect(target, f"Tu as été expulsé par {username}.")
            broadcast(f"[SERVER] {target_name} a été expulsé.")
            print(f"[SERVER] {username} a kick {target_name}")
        elif cmd == "/mute":
            with clients_lock:
                clients[target]["muted"] = True
            send(target, "[SERVER] Tu as été réduit au silence.")
            send(conn, f"[SERVER] {target_name} est maintenant muet.")
        else:
            with clients_lock:
                clients[target]["muted"] = False
            send(target, "[SERVER] Tu peux à nouveau parler.")
            send(conn, f"[SERVER] {target_name} n'est plus muet.")
        return True, None

    if cmd in ("/ban", "/unban"):
        if not has_level(my_role(conn), "admin"):
            send(conn, "[SERVER] Commande réservée aux admins.")
            return True, None
        if len(parts) < 2:
            send(conn, f"[SERVER] Usage : {cmd} <pseudo>")
            return True, None
        target_name = parts[1]
        if target_name == username:
            send(conn, "[SERVER] Tu ne peux pas te bannir toi-même.")
            return True, None
        value = cmd == "/ban"
        if not set_banned_in_file(target_name, value):
            send(conn, f"[SERVER] Utilisateur '{target_name}' introuvable.")
            return True, None
        if value:
            target = find_conn_by_name(target_name)
            if target is not None:
                disconnect(target, f"Tu as été banni par {username}.")
            broadcast(f"[SERVER] {target_name} a été banni.")
            print(f"[SERVER] {username} a ban {target_name}")
        else:
            send(conn, f"[SERVER] {target_name} a été débanni.")
        return True, None

    if cmd == "/online":
        with clients_lock:
            listing = ", ".join(f"{i['username']} ({i['role']}, {i['room']})" for i in clients.values())
        send(conn, f"[SERVER] Connectés : {listing}")
        return True, None

    if cmd == "/rooms":
        with rooms_lock:
            listing = ", ".join(sorted(rooms))
        send(conn, f"[SERVER] Salons : {listing}")
        return True, None

    if cmd == "/join":
        if len(parts) < 2:
            send(conn, "[SERVER] Usage : /join <salon>")
            return True, None
        room_name = parts[1]
        with clients_lock:
            old_room = clients[conn]["room"]
        if room_name == old_room:
            send(conn, "[SERVER] Tu es déjà dans ce salon.")
            return True, None
        with rooms_lock:
            rooms.add(room_name)
        broadcast(f"[SERVER] {username} a quitté le salon.", room=old_room, exclude_conn=conn)
        with clients_lock:
            clients[conn]["room"] = room_name
        prune_room(old_room)
        broadcast(f"[SERVER] {username} a rejoint le salon.", room=room_name, exclude_conn=conn)
        send(conn, f"[SERVER] Tu es maintenant dans le salon '{room_name}'.")
        return True, None

    if cmd == "/leave":
        with clients_lock:
            old_room = clients[conn]["room"]
        if old_room == DEFAULT_ROOM:
            send(conn, "[SERVER] Tu es déjà dans le salon général.")
            return True, None
        broadcast(f"[SERVER] {username} a quitté le salon.", room=old_room, exclude_conn=conn)
        with clients_lock:
            clients[conn]["room"] = DEFAULT_ROOM
        prune_room(old_room)
        broadcast(f"[SERVER] {username} a rejoint le salon.", room=DEFAULT_ROOM, exclude_conn=conn)
        send(conn, f"[SERVER] Tu es de retour dans le salon '{DEFAULT_ROOM}'.")
        return True, None

    return False, None


def handle_client(conn, addr):
    print(f"[SERVER] New connection : {addr}")
    username = None
    joined = False
    conn.settimeout(TIMEOUT)
    buffer = ""
    try:
        while "\n" not in buffer:
            data = conn.recv(1024)
            if not data:
                return
            buffer += data.decode(FORMAT, errors="replace")
        line, buffer = buffer.split("\n", 1)
        username = clean_text(line.strip())

        if not valid_username(username):
            send(conn, "[SERVER] Pseudo invalide (3-20 caractères : lettres, chiffres, _ ou -).")
            print(f"[SERVER] Pseudo refusé ({addr})")
            return

        if is_banned(username):
            send(conn, "[SERVER] Tu es banni de ce serveur.")
            print(f"[SERVER] {username} banni, connexion refusée ({addr})")
            return

        role = register_user(addr, username)

        with clients_lock:
            clients[conn] = {"username": username, "role": role, "muted": False,
                             "addr": addr, "room": DEFAULT_ROOM}
        joined = True

        send(conn, f"Bienvenue {username} ! (rôle : {role})")
        broadcast(f"[SERVER] {username} a rejoint le chat.", room=DEFAULT_ROOM, exclude_conn=conn)
        print(f"[SERVER] {username} joined ({addr}) role={role}")

        last_active = time.time()
        conn.settimeout(CHECK_INTERVAL)
        disconnect_flag = False

        while not disconnect_flag:
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                msg = clean_text(line.strip())
                if not msg:
                    continue
                if len(msg) > MAX_MSG_LEN:
                    msg = msg[:MAX_MSG_LEN]

                if msg == DISCONNECT_MESSAGE:
                    disconnect_flag = True
                    break

                if msg.split()[0].lower() not in PASSIVE_COMMANDS:
                    last_active = time.time()

                if msg.startswith("/"):
                    handled, new_name = handle_command(conn, addr, username, msg)
                    if not handled:
                        send(conn, f"[SERVER] Commande inconnue : {msg}")
                    elif new_name:
                        username = new_name
                    continue

                with clients_lock:
                    info = clients.get(conn)
                    muted = info["muted"] if info else False
                    room = info["room"] if info else DEFAULT_ROOM
                if muted:
                    send(conn, "[SERVER] Tu es réduit au silence, ton message n'a pas été envoyé.")
                    continue

                print(f"[{room}][{username}] {msg}")
                broadcast(f"[{stamp()}] [{username}] {msg}", room=room, exclude_conn=conn)

            if disconnect_flag:
                break

            try:
                data = conn.recv(1024)
            except socket.timeout:
                if time.time() - last_active > TIMEOUT:
                    send(conn, "[SERVER] Déconnecté pour inactivité.")
                    print(f"[SERVER] {addr} timeout.")
                    break
                continue
            if not data:
                break
            buffer += data.decode(FORMAT, errors="replace")

    except socket.timeout:
        send(conn, "[SERVER] Déconnecté pour inactivité.")
        print(f"[SERVER] {addr} timeout.")
    except ConnectionResetError:
        print(f"[SERVER] ERROR : {addr} disconnected.")
    except OSError:
        print(f"[SERVER] {addr} socket closed.")
    finally:
        with clients_lock:
            info = clients.pop(conn, None)
        conn.close()
        if joined:
            room = info["room"] if info else DEFAULT_ROOM
            broadcast(f"[SERVER] {username} a quitté le chat.", room=room)
            prune_room(room)
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
