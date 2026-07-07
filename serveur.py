######################################################################################
# server.py
######################################################################################
import socket
import threading
import os
import json
import datetime
import re

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


def clean_text(text):
    return "".join(ch for ch in text if ch.isprintable())


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
            try:
                conn.sendall(message.encode(FORMAT))
            except OSError:
                pass


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
    try:
        target_conn.sendall(f"[SERVER] {reason}".encode(FORMAT))
        target_conn.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass


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

    if cmd == "/role":
        conn.sendall(f"[SERVER] Ton rôle : {my_role(conn)}.".encode(FORMAT))
        return True, None

    if cmd == "/rename":
        if len(parts) < 2:
            conn.sendall("[SERVER] Usage : /rename <nouveau_pseudo>".encode(FORMAT))
            return True, None
        new_name = parts[1]
        if not valid_username(new_name):
            conn.sendall("[SERVER] Pseudo invalide (3-20 caractères : lettres, chiffres, _ ou -).".encode(FORMAT))
            return True, None
        with clients_lock:
            taken = any(info["username"] == new_name for info in clients.values())
        if taken:
            conn.sendall("[SERVER] Ce pseudo est déjà pris.".encode(FORMAT))
            return True, None
        current_role = my_role(conn)
        register_user(addr, new_name)
        set_role_in_file(new_name, current_role)
        with clients_lock:
            if conn in clients:
                clients[conn]["username"] = new_name
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

    if cmd in ("/setadmin", "/setmodo", "/remadmin", "/remmodo"):
        if not has_level(my_role(conn), "admin"):
            conn.sendall("[SERVER] Commande réservée aux admins.".encode(FORMAT))
            return True, None
        if len(parts) < 2:
            conn.sendall(f"[SERVER] Usage : {cmd} <pseudo>".encode(FORMAT))
            return True, None
        target_name = parts[1]
        if cmd == "/setadmin":
            new_role = "admin"
        elif cmd == "/setmodo":
            new_role = "moderateur"
        else:
            new_role = "user"
        if not set_role_in_file(target_name, new_role):
            conn.sendall(f"[SERVER] Utilisateur '{target_name}' introuvable.".encode(FORMAT))
            return True, None
        target = find_conn_by_name(target_name)
        if target is not None:
            with clients_lock:
                clients[target]["role"] = new_role
            target.sendall(f"[SERVER] Ton rôle est maintenant : {new_role}.".encode(FORMAT))
        conn.sendall(f"[SERVER] {target_name} est maintenant {new_role}.".encode(FORMAT))
        print(f"[SERVER] {username} a mis {target_name} en {new_role}")
        return True, None

    if cmd in ("/kick", "/mute", "/unmute"):
        if not has_level(my_role(conn), "moderateur"):
            conn.sendall("[SERVER] Commande réservée aux modérateurs et admins.".encode(FORMAT))
            return True, None
        if len(parts) < 2:
            conn.sendall(f"[SERVER] Usage : {cmd} <pseudo>".encode(FORMAT))
            return True, None
        target_name = parts[1]
        target = find_conn_by_name(target_name)
        if target is None:
            conn.sendall(f"[SERVER] Utilisateur '{target_name}' introuvable.".encode(FORMAT))
            return True, None
        if not can_moderate(conn, target):
            conn.sendall("[SERVER] Tu ne peux pas modérer cet utilisateur.".encode(FORMAT))
            return True, None

        if cmd == "/kick":
            disconnect(target, f"Tu as été expulsé par {username}.")
            broadcast(f"[SERVER] {target_name} a été expulsé.")
            print(f"[SERVER] {username} a kick {target_name}")
        elif cmd == "/mute":
            with clients_lock:
                clients[target]["muted"] = True
            target.sendall("[SERVER] Tu as été réduit au silence.".encode(FORMAT))
            conn.sendall(f"[SERVER] {target_name} est maintenant muet.".encode(FORMAT))
        else:
            with clients_lock:
                clients[target]["muted"] = False
            target.sendall("[SERVER] Tu peux à nouveau parler.".encode(FORMAT))
            conn.sendall(f"[SERVER] {target_name} n'est plus muet.".encode(FORMAT))
        return True, None

    if cmd in ("/ban", "/unban"):
        if not has_level(my_role(conn), "admin"):
            conn.sendall("[SERVER] Commande réservée aux admins.".encode(FORMAT))
            return True, None
        if len(parts) < 2:
            conn.sendall(f"[SERVER] Usage : {cmd} <pseudo>".encode(FORMAT))
            return True, None
        target_name = parts[1]
        if target_name == username:
            conn.sendall("[SERVER] Tu ne peux pas te bannir toi-même.".encode(FORMAT))
            return True, None
        value = cmd == "/ban"
        if not set_banned_in_file(target_name, value):
            conn.sendall(f"[SERVER] Utilisateur '{target_name}' introuvable.".encode(FORMAT))
            return True, None
        if value:
            target = find_conn_by_name(target_name)
            if target is not None:
                disconnect(target, f"Tu as été banni par {username}.")
            broadcast(f"[SERVER] {target_name} a été banni.")
            print(f"[SERVER] {username} a ban {target_name}")
        else:
            conn.sendall(f"[SERVER] {target_name} a été débanni.".encode(FORMAT))
        return True, None

    if cmd == "/online":
        with clients_lock:
            listing = ", ".join(f"{i['username']} ({i['role']}, {i['room']})" for i in clients.values())
        conn.sendall(f"[SERVER] Connectés : {listing}".encode(FORMAT))
        return True, None

    if cmd == "/rooms":
        with rooms_lock:
            listing = ", ".join(sorted(rooms))
        conn.sendall(f"[SERVER] Salons : {listing}".encode(FORMAT))
        return True, None

    if cmd == "/join":
        if len(parts) < 2:
            conn.sendall("[SERVER] Usage : /join <salon>".encode(FORMAT))
            return True, None
        room_name = parts[1]
        with clients_lock:
            old_room = clients[conn]["room"]
        if room_name == old_room:
            conn.sendall("[SERVER] Tu es déjà dans ce salon.".encode(FORMAT))
            return True, None
        with rooms_lock:
            rooms.add(room_name)
        broadcast(f"[SERVER] {username} a quitté le salon.", room=old_room, exclude_conn=conn)
        with clients_lock:
            clients[conn]["room"] = room_name
        prune_room(old_room)
        broadcast(f"[SERVER] {username} a rejoint le salon.", room=room_name, exclude_conn=conn)
        conn.sendall(f"[SERVER] Tu es maintenant dans le salon '{room_name}'.".encode(FORMAT))
        return True, None

    if cmd == "/leave":
        with clients_lock:
            old_room = clients[conn]["room"]
        if old_room == DEFAULT_ROOM:
            conn.sendall("[SERVER] Tu es déjà dans le salon général.".encode(FORMAT))
            return True, None
        broadcast(f"[SERVER] {username} a quitté le salon.", room=old_room, exclude_conn=conn)
        with clients_lock:
            clients[conn]["room"] = DEFAULT_ROOM
        prune_room(old_room)
        broadcast(f"[SERVER] {username} a rejoint le salon.", room=DEFAULT_ROOM, exclude_conn=conn)
        conn.sendall(f"[SERVER] Tu es de retour dans le salon '{DEFAULT_ROOM}'.".encode(FORMAT))
        return True, None

    return False, None


def handle_client(conn, addr):
    print(f"[SERVER] New connection : {addr}")
    username = None
    joined = False
    conn.settimeout(TIMEOUT)
    try:
        data = conn.recv(1024)
        if not data:
            return
        username = clean_text(data.decode(FORMAT, errors="replace").strip())

        if not valid_username(username):
            conn.sendall("[SERVER] Pseudo invalide (3-20 caractères : lettres, chiffres, _ ou -).".encode(FORMAT))
            print(f"[SERVER] Pseudo refusé ({addr})")
            return

        if is_banned(username):
            conn.sendall("[SERVER] Tu es banni de ce serveur.".encode(FORMAT))
            print(f"[SERVER] {username} banni, connexion refusée ({addr})")
            return

        role = register_user(addr, username)

        with clients_lock:
            clients[conn] = {"username": username, "role": role, "muted": False,
                             "addr": addr, "room": DEFAULT_ROOM}
        joined = True

        conn.sendall(f"Bienvenue {username} ! (rôle : {role})".encode(FORMAT))
        broadcast(f"[SERVER] {username} a rejoint le chat.", room=DEFAULT_ROOM, exclude_conn=conn)
        print(f"[SERVER] {username} joined ({addr}) role={role}")

        while True:
            data = conn.recv(1024)
            if not data:
                break
            msg = clean_text(data.decode(FORMAT, errors="replace").strip())
            if not msg:
                continue
            if len(msg) > MAX_MSG_LEN:
                msg = msg[:MAX_MSG_LEN]

            if msg == DISCONNECT_MESSAGE:
                break

            if msg.startswith("/"):
                handled, new_name = handle_command(conn, addr, username, msg)
                if not handled:
                    conn.sendall(f"[SERVER] Commande inconnue : {msg}".encode(FORMAT))
                elif new_name:
                    username = new_name
                continue

            with clients_lock:
                info = clients.get(conn)
                muted = info["muted"] if info else False
                room = info["room"] if info else DEFAULT_ROOM
            if muted:
                conn.sendall("[SERVER] Tu es réduit au silence, ton message n'a pas été envoyé.".encode(FORMAT))
                continue

            print(f"[{room}][{username}] {msg}")
            broadcast(f"[{username}] {msg}", room=room, exclude_conn=conn)

    except socket.timeout:
        try:
            conn.sendall("[SERVER] Déconnecté pour inactivité.".encode(FORMAT))
        except OSError:
            pass
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
