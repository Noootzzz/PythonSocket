######################################################################################
# client_gui.py
######################################################################################

import socket
import threading
import queue
import time
import sys
import re
import datetime
import tkinter as tk
from tkinter import messagebox

SERVER = socket.gethostbyname(socket.gethostname())
PORT = 5000
ADDR = (SERVER, PORT)
FORMAT = 'utf-8'
DISCONNECT_MESSAGE = "/quit"
USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]{3,20}$")

# --- Thème : NEO-BRUTALISM ---
BG = "#f3efe4"
BLACK = "#161616"
WHITE = "#ffffff"
YELLOW = "#ffd23e"
PINK = "#ff6ba6"
CYAN = "#54d1c4"
PURPLE = "#b491ff"
LIME = "#c3f53f"
ORANGE = "#ff8a3d"
GREY = "#7a7a70"
ACCENT_RED = "#e23b3b"
PLACEHOLDER = "Écris un message…"

AVATAR_COLORS = [YELLOW, PINK, CYAN, PURPLE, LIME, ORANGE]
ROLE_BG = {"user": WHITE, "moderateur": YELLOW, "admin": PINK}
BUBBLE_ME = CYAN
BUBBLE_OTHER = WHITE
BUBBLE_MP = PURPLE

TITLE_FONT = ("Arial Black", 15)
HEAD_FONT = ("Arial Black", 11)
BOLD = ("Segoe UI", 10, "bold")
BODY = ("Segoe UI", 11)

# Géométrie du chat
PAD = 10
AV = 34
GAP = 10
SHADOW = 5
BUBBLE_MAXW = 300

ROOM_RE = re.compile(r"salon '([^']+)'")
ROLE_RE = re.compile(r"rôle(?: est maintenant)?\s*:\s*(\w+)")
RENAME_RE = re.compile(r"Tu es maintenant '([^']+)'")
USER_RE = re.compile(r"(\S+) \((\w+), ([^)]+)\)")
MSG_RE = re.compile(r"^\[(\d\d:\d\d)\] \[([^\]]+)\] (.*)$")
ROLE_DISPLAY = {"user": "user", "moderateur": "modo", "admin": "admin"}

SECTIONS = [
    ("Général", [
        ("/rename <pseudo>", "changer de pseudo", None),
        ("/mp <pseudo> <msg>", "message privé", None),
        ("/role", "voir ton rôle", None),
        ("/time", "heure du serveur", None),
        ("/ping", "latence", None),
        ("/clear", "vider le chat", None),
        ("/quit", "quitter", None),
    ]),
    ("Salons", [
        ("/online", "qui est connecté", None),
        ("/rooms", "liste des salons", None),
        ("/join <salon>", "rejoindre / créer", None),
        ("/leave", "revenir au général", None),
    ]),
    ("Modération", [
        ("/kick <pseudo>", "expulser", "modo"),
        ("/mute <pseudo>", "rendre muet", "modo"),
        ("/unmute <pseudo>", "rétablir", "modo"),
        ("/ban <pseudo>", "bannir", "admin"),
        ("/unban <pseudo>", "débannir", "admin"),
        ("/setModo <pseudo>", "promouvoir modo", "admin"),
        ("/remModo <pseudo>", "retirer modo", "admin"),
        ("/setAdmin <pseudo>", "promouvoir admin", "admin"),
        ("/remAdmin <pseudo>", "retirer admin", "admin"),
    ]),
]

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
running = True
ping_time = None
last_reason = None
msg_queue = queue.Queue()

name = None
current_room = "general"
known_rooms = ["general"]
online_users = []
history = []
hist_index = None
messages = []
last_width = 0


def receive():
    buffer = ""
    while running:
        try:
            data = client.recv(1024)
        except OSError:
            break
        if not data:
            break
        buffer += data.decode(FORMAT, errors="replace")
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            if line:
                msg_queue.put(line)
    msg_queue.put(None)


def send_raw(text):
    try:
        client.sendall((text + "\n").encode(FORMAT))
    except OSError:
        pass


# ----- Chat brutaliste (Canvas) -----
def avatar_color(person):
    return AVATAR_COLORS[sum(map(ord, person)) % len(AVATAR_COLORS)] if person else WHITE


def draw_message(msg, width, y):
    if msg["kind"] == "system":
        tid = canvas.create_text(width // 2, y + 4, text=msg["text"],
                                 width=max(width - 140, 120), anchor="n",
                                 font=("Segoe UI", 9, "bold"), fill=GREY, justify="center")
        return canvas.bbox(tid)[3] + 12

    kind = msg["kind"]
    right = kind in ("me", "mp_out")
    if kind == "me":
        color = BUBBLE_ME
    elif kind in ("mp_in", "mp_out"):
        color = BUBBLE_MP
    else:
        color = BUBBLE_OTHER

    cy = y + PAD
    ids = []
    if msg["label"]:
        nid = canvas.create_text(PAD, cy, text=msg["label"].upper(), anchor="nw",
                                 font=("Segoe UI", 8, "bold"), fill=BLACK)
        ids.append(nid)
        cy = canvas.bbox(nid)[3] + 2
    tid = canvas.create_text(PAD, cy, text=msg["text"], width=BUBBLE_MAXW,
                             anchor="nw", font=("Segoe UI", 11), fill=BLACK)
    ids.append(tid)
    cy = canvas.bbox(tid)[3] + 2
    wid = canvas.create_text(PAD, cy, text=msg["when"], anchor="nw",
                             font=("Segoe UI", 8), fill="#555555")
    ids.append(wid)

    x2 = max(canvas.bbox(i)[2] for i in ids)
    bottom = canvas.bbox(wid)[3]
    bw = x2 + PAD
    bh_bottom = bottom + PAD

    if right:
        avatar_x = width - 16 - AV
        bubble_x = avatar_x - GAP - bw
    else:
        avatar_x = 16
        bubble_x = avatar_x + AV + GAP

    for i in ids:
        canvas.move(i, bubble_x, 0)

    shadow = canvas.create_rectangle(bubble_x + SHADOW, y + SHADOW,
                                     bubble_x + bw + SHADOW, bh_bottom + SHADOW,
                                     fill=BLACK, outline="")
    rect = canvas.create_rectangle(bubble_x, y, bubble_x + bw, bh_bottom,
                                   fill=color, outline=BLACK, width=3)
    canvas.tag_lower(rect, ids[0])
    canvas.tag_lower(shadow, rect)

    person = msg["person"] or "?"
    canvas.create_rectangle(avatar_x + SHADOW, y + SHADOW,
                            avatar_x + AV + SHADOW, y + AV + SHADOW, fill=BLACK, outline="")
    canvas.create_rectangle(avatar_x, y, avatar_x + AV, y + AV,
                            fill=avatar_color(person), outline=BLACK, width=3)
    canvas.create_text(avatar_x + AV / 2, y + AV / 2, text=person[0].upper(),
                       fill=BLACK, font=("Arial Black", 11))

    return max(bh_bottom, y + AV) + GAP + SHADOW


def redraw_chat(event=None):
    canvas.delete("all")
    width = canvas.winfo_width()
    height = canvas.winfo_height()
    if width < 20:
        return
    y = 16
    for msg in messages:
        y = draw_message(msg, width, y)
    canvas.configure(scrollregion=(0, 0, width, max(y + 6, height)))


def scroll_bottom():
    canvas.update_idletasks()
    canvas.yview_moveto(1.0)


def add_system(text):
    messages.append({"kind": "system", "text": text})
    redraw_chat()
    scroll_bottom()


def add_message(line, mine=False):
    m = MSG_RE.match(line)
    if not m:
        add_system(line)
        return
    when, who, text = m.groups()
    if mine:
        kind, person, label = "me", name, None
    elif who.startswith("MP à "):
        kind, person, label = "mp_out", who[5:], who
    elif who.startswith("MP de "):
        kind, person, label = "mp_in", who[6:], who
    else:
        kind, person, label = "other", who, who
    messages.append({"kind": kind, "person": person, "label": label,
                     "text": text, "when": when})
    redraw_chat()
    scroll_bottom()


def clear_chat():
    messages.clear()
    redraw_chat()


def on_canvas_resize(event):
    global last_width
    if abs(event.width - last_width) > 2:
        last_width = event.width
        redraw_chat()


# ----- Salons (onglets) -----
def render_tabs():
    for w in tabbar.winfo_children():
        w.destroy()
    for room in known_rooms:
        active = room == current_room
        tab = tk.Label(tabbar, text=f"# {room}".upper(),
                       bg=YELLOW if active else WHITE, fg=BLACK,
                       font=("Segoe UI", 9, "bold"),
                       padx=12, pady=5, cursor="hand2",
                       highlightbackground=BLACK, highlightthickness=2)
        tab.pack(side=tk.LEFT, padx=(0, 6))
        tab.bind("<Button-1>", lambda e, r=room: switch_room(r))
    plus = tk.Label(tabbar, text="+", bg=WHITE, fg=BLACK,
                    font=("Arial Black", 10), padx=10, pady=3, cursor="hand2",
                    highlightbackground=BLACK, highlightthickness=2)
    plus.pack(side=tk.LEFT)
    plus.bind("<Button-1>", lambda e: create_room())


def switch_room(room):
    if room != current_room:
        send_raw(f"/join {room}")


def themed_input(title, label_text, action):
    win = tk.Toplevel(root)
    win.title(title)
    win.configure(bg=BG)
    win.resizable(False, False)
    win.transient(root)
    w, h = 360, 210
    x = root.winfo_x() + (root.winfo_width() // 2) - (w // 2)
    y = root.winfo_y() + (root.winfo_height() // 2) - (h // 2)
    win.geometry(f"{w}x{h}+{max(x, 0)}+{max(y, 0)}")

    result = {"value": None}

    tk.Label(win, text=label_text.upper(), bg=BG, fg=BLACK,
             font=HEAD_FONT).pack(pady=(26, 12))
    field = tk.Frame(win, bg=WHITE, highlightbackground=BLACK, highlightthickness=3)
    field.pack(fill=tk.X, padx=28)
    box = tk.Entry(field, bg=WHITE, fg=BLACK, insertbackground=BLACK,
                   font=("Segoe UI", 12), borderwidth=0, highlightthickness=0)
    box.pack(fill=tk.X, ipady=9, padx=10)

    def ok(event=None):
        value = box.get().strip()
        if value:
            result["value"] = value
        win.destroy()

    box.bind("<Return>", ok)
    buttons = tk.Frame(win, bg=BG)
    buttons.pack(fill=tk.X, padx=28, pady=20)
    tk.Button(buttons, text=action.upper(), command=ok, bg=PINK, fg=BLACK,
              activebackground=PINK, activeforeground=BLACK, borderwidth=0,
              relief=tk.FLAT, font=("Segoe UI", 10, "bold"), cursor="hand2",
              padx=16, highlightbackground=BLACK, highlightthickness=3).pack(
        side=tk.RIGHT, ipady=4)
    tk.Button(buttons, text="ANNULER", command=win.destroy, bg=WHITE, fg=BLACK,
              activebackground=WHITE, activeforeground=BLACK, borderwidth=0,
              relief=tk.FLAT, font=("Segoe UI", 10, "bold"), cursor="hand2",
              padx=16, highlightbackground=BLACK, highlightthickness=3).pack(
        side=tk.RIGHT, padx=(0, 10), ipady=4)

    box.focus()
    win.grab_set()
    root.wait_window(win)
    return result["value"]


def create_room():
    room = themed_input("Nouveau salon", "Nom du salon", "Créer")
    if room:
        send_raw(f"/join {room}")


def set_rooms(rooms):
    global known_rooms
    known_rooms = rooms[:]
    if current_room not in known_rooms:
        known_rooms.append(current_room)
    render_tabs()


# ----- Panneau des connectés -----
def render_users():
    for w in users_list.winfo_children():
        w.destroy()
    users_header.config(text=f"EN LIGNE · {len(online_users)}")
    if not online_users:
        tk.Label(users_list, text="…", bg=WHITE, fg=GREY,
                 font=BODY).pack(anchor=tk.W, padx=16, pady=6)
        return
    order = {"admin": 0, "moderateur": 1, "user": 2}
    ordered = sorted(online_users, key=lambda u: (order.get(u[1], 3), u[0].lower()))
    for uname, role, room in ordered:
        row = tk.Frame(users_list, bg=WHITE)
        row.pack(fill=tk.X, padx=12, pady=4)
        chip = tk.Label(row, text=" ", bg=ROLE_BG.get(role, WHITE),
                        highlightbackground=BLACK, highlightthickness=2)
        chip.pack(side=tk.LEFT, padx=(0, 6))
        tk.Label(row, text=uname, bg=WHITE, fg=BLACK,
                 font=BOLD).pack(side=tk.LEFT)
        tk.Label(row, text=ROLE_DISPLAY.get(role, role).upper(), bg=WHITE,
                 fg=GREY, font=("Segoe UI", 8, "bold")).pack(side=tk.RIGHT)


def set_users(users):
    global online_users
    online_users = users
    render_users()


def handle_special(line):
    if line.startswith("[SERVER] Salons :"):
        rest = line.split("Salons :", 1)[1].strip()
        set_rooms([r.strip() for r in rest.split(",") if r.strip()])
        return True
    if line.startswith("[SERVER] Connectés :"):
        rest = line.split("Connectés :", 1)[1]
        set_users(USER_RE.findall(rest))
        return True
    return False


def update_meta(line):
    global current_room, name
    room = ROOM_RE.search(line)
    if room:
        current_room = room.group(1)
        room_label.config(text=f"# {current_room}".upper())
        if current_room not in known_rooms:
            known_rooms.append(current_room)
        render_tabs()
    role = ROLE_RE.search(line)
    if role:
        value = role.group(1)
        role_label.config(text=ROLE_DISPLAY.get(value, value).upper(),
                          bg=ROLE_BG.get(value, WHITE))
    renamed = RENAME_RE.search(line)
    if renamed:
        name = renamed.group(1)
        pseudo_label.config(text=name.upper())


def maybe_bell(line):
    if MSG_RE.match(line):
        try:
            root.bell()
        except tk.TclError:
            pass


def track_reason(line):
    global last_reason
    low = line.lower()
    if "inactivité" in low:
        last_reason = "Tu as été déconnecté pour inactivité."
    elif "tu as été expulsé" in low:
        last_reason = "Tu as été expulsé du serveur."
    elif "tu as été banni" in low:
        last_reason = "Tu as été banni du serveur."


def forced_disconnect():
    global running
    running = False
    try:
        client.close()
    except OSError:
        pass
    messagebox.showinfo("Déconnecté", last_reason or "Tu as été déconnecté du serveur.")
    root.destroy()


def poll_queue():
    while not msg_queue.empty():
        item = msg_queue.get()
        if item is None:
            if running:
                forced_disconnect()
            return
        if item == "/pong":
            latency = (time.time() - ping_time) * 1000
            add_system(f"Ping : {latency:.0f} ms")
            continue
        if handle_special(item):
            continue
        update_meta(item)
        track_reason(item)
        maybe_bell(item)
        add_message(item)
    if running:
        root.after(100, poll_queue)


refresh_next = "/rooms"


def refresh_state():
    global refresh_next
    if running:
        send_raw(refresh_next)
        refresh_next = "/online" if refresh_next == "/rooms" else "/rooms"
        root.after(2500, refresh_state)


# ----- Saisie -----
def entry_text():
    value = entry.get()
    if value == PLACEHOLDER:
        return ""
    return value.strip()


def clear_placeholder():
    if entry.get() == PLACEHOLDER:
        entry.delete(0, tk.END)
        entry.config(fg=BLACK)


def set_entry(text):
    clear_placeholder()
    entry.delete(0, tk.END)
    entry.insert(0, text)
    entry.config(fg=BLACK)
    entry.icursor(tk.END)


def send_message(event=None):
    global ping_time, hist_index
    message = entry_text()
    if not message:
        return
    entry.delete(0, tk.END)
    history.append(message)
    hist_index = None

    if message == "/clear":
        clear_chat()
        return

    if message == "/ping":
        ping_time = time.time()

    try:
        client.sendall((message + "\n").encode(FORMAT))
    except OSError:
        add_system("Erreur : impossible d'envoyer.")
        return

    if not message.startswith("/"):
        now = datetime.datetime.now().strftime("%H:%M")
        add_message(f"[{now}] [{name}] {message}", mine=True)

    if message == DISCONNECT_MESSAGE:
        on_close()


def hist_up(event):
    global hist_index
    if not history:
        return "break"
    hist_index = len(history) - 1 if hist_index is None else max(0, hist_index - 1)
    set_entry(history[hist_index])
    return "break"


def hist_down(event):
    global hist_index
    if hist_index is None:
        return "break"
    hist_index += 1
    if hist_index >= len(history):
        hist_index = None
        set_entry("")
    else:
        set_entry(history[hist_index])
    return "break"


def on_close():
    global running
    if running:
        running = False
        try:
            client.sendall((DISCONNECT_MESSAGE + "\n").encode(FORMAT))
        except OSError:
            pass
        try:
            client.close()
        except OSError:
            pass
    root.destroy()


def on_entry_focus_in(event):
    clear_placeholder()


def on_entry_focus_out(event):
    if not entry.get():
        entry.insert(0, PLACEHOLDER)
        entry.config(fg=GREY)


def insert_command(event):
    idx = panel.index(f"@{event.x},{event.y}")
    line = panel.get(f"{idx} linestart", f"{idx} lineend").strip()
    if not line:
        return
    token = line.split()[0]
    if token.startswith("/"):
        entry.focus()
        set_entry(token + " ")


# ----- Écran de connexion -----
def ask_username():
    win = tk.Toplevel(root)
    win.title("Connexion")
    win.configure(bg=BG)
    win.resizable(False, False)
    w, h = 380, 270
    x = (win.winfo_screenwidth() // 2) - (w // 2)
    y = (win.winfo_screenheight() // 2) - (h // 2)
    win.geometry(f"{w}x{h}+{x}+{y}")

    result = {"name": None}

    tk.Label(win, text="BIENVENUE 👋", bg=BG, fg=BLACK,
             font=("Arial Black", 16)).pack(pady=(30, 4))
    tk.Label(win, text="Choisis ton pseudo", bg=BG, fg=GREY,
             font=BODY).pack()

    field = tk.Frame(win, bg=WHITE, highlightbackground=BLACK, highlightthickness=3)
    field.pack(fill=tk.X, padx=32, pady=(18, 6))
    box = tk.Entry(field, bg=WHITE, fg=BLACK, insertbackground=BLACK,
                   font=("Segoe UI", 13), borderwidth=0, highlightthickness=0,
                   justify=tk.CENTER)
    box.pack(fill=tk.X, ipady=10, padx=10)
    box.focus()

    hint = tk.Label(win, text="3 à 20 caractères : lettres, chiffres, _ ou -",
                    bg=BG, fg=GREY, font=("Segoe UI", 8))
    hint.pack()

    def submit(event=None):
        value = box.get().strip()
        if not USERNAME_RE.match(value):
            hint.config(text="Pseudo invalide (3-20 : lettres, chiffres, _ ou -)", fg=ACCENT_RED)
            return
        result["name"] = value
        win.destroy()

    box.bind("<Return>", submit)
    tk.Button(win, text="REJOINDRE LE CHAT", command=submit,
              bg=YELLOW, fg=BLACK, activebackground=YELLOW, activeforeground=BLACK,
              borderwidth=0, relief=tk.FLAT, font=("Segoe UI", 11, "bold"),
              cursor="hand2", highlightbackground=BLACK, highlightthickness=3).pack(
        fill=tk.X, padx=32, pady=18, ipady=8)

    win.protocol("WM_DELETE_WINDOW", lambda: (root.destroy(), sys.exit()))
    root.wait_window(win)
    return result["name"]


# ----- Lancement -----
root = tk.Tk()
root.withdraw()

name = ask_username()
if not name:
    root.destroy()
    sys.exit()

try:
    client.connect(ADDR)
    client.sendall((name + "\n").encode(FORMAT))
except OSError as e:
    messagebox.showerror("Connexion", f"Impossible de se connecter au serveur.\n{e}")
    root.destroy()
    sys.exit()

# ----- Fenêtre principale -----
root.deiconify()
root.title("Chat")
root.geometry("1020x620")
root.minsize(840, 500)
root.configure(bg=BG)

header = tk.Frame(root, bg=BG)
header.pack(side=tk.TOP, fill=tk.X, padx=22, pady=(16, 12))
tk.Label(header, text="CHAT", bg=YELLOW, fg=BLACK, font=TITLE_FONT,
         padx=14, pady=4, highlightbackground=BLACK, highlightthickness=3).pack(side=tk.LEFT)

pseudo_label = tk.Label(header, text=name.upper(), bg=BG, fg=BLACK, font=BOLD)
pseudo_label.pack(side=tk.RIGHT, padx=(12, 0))
role_label = tk.Label(header, text="USER", bg=WHITE, fg=BLACK,
                      font=("Segoe UI", 9, "bold"), padx=8, pady=3,
                      highlightbackground=BLACK, highlightthickness=2)
role_label.pack(side=tk.RIGHT, padx=(8, 0))
room_label = tk.Label(header, text="# GENERAL", bg=CYAN, fg=BLACK,
                      font=("Segoe UI", 9, "bold"), padx=8, pady=3,
                      highlightbackground=BLACK, highlightthickness=2)
room_label.pack(side=tk.RIGHT)

content = tk.Frame(root, bg=BG)
content.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=22, pady=(0, 10))

# Colonne gauche : commandes
sidebar = tk.Frame(content, bg=WHITE, width=232,
                   highlightbackground=BLACK, highlightthickness=3)
sidebar.pack(side=tk.LEFT, fill=tk.Y)
sidebar.pack_propagate(False)
tk.Label(sidebar, text="COMMANDES", bg=WHITE, fg=BLACK,
         font=HEAD_FONT).pack(anchor=tk.W, padx=14, pady=(12, 6))
panel = tk.Text(sidebar, bg=WHITE, fg=BLACK, borderwidth=0, highlightthickness=0,
                wrap=tk.NONE, cursor="arrow", padx=12, pady=4, width=1)
panel.pack(fill=tk.BOTH, expand=True)
panel.tag_config("sec", foreground=BLACK, font=("Arial Black", 9), spacing1=10)
panel.tag_config("cmd", foreground=BLACK, font=("Consolas", 10, "bold"))
panel.tag_config("desc", foreground=GREY, font=("Segoe UI", 8), spacing3=4)
panel.tag_config("modo", foreground="#a9791f", font=("Segoe UI", 8, "bold"))
panel.tag_config("admin", foreground="#c23f6a", font=("Segoe UI", 8, "bold"))
panel.tag_bind("cmd", "<Button-1>", insert_command)
panel.tag_bind("cmd", "<Enter>", lambda e: panel.config(cursor="hand2"))
panel.tag_bind("cmd", "<Leave>", lambda e: panel.config(cursor="arrow"))
panel.bind("<MouseWheel>", lambda e: panel.yview_scroll(int(-e.delta / 120), "units"))
for section, cmds in SECTIONS:
    panel.insert(tk.END, section.upper() + "\n", "sec")
    for cname, desc, role in cmds:
        panel.insert(tk.END, cname + "\n", "cmd")
        panel.insert(tk.END, "   " + desc, "desc")
        if role:
            panel.insert(tk.END, "  " + role, role)
        panel.insert(tk.END, "\n", "desc")
panel.config(state=tk.DISABLED)

# Colonne droite : connectés
users = tk.Frame(content, bg=WHITE, width=196,
                 highlightbackground=BLACK, highlightthickness=3)
users.pack(side=tk.RIGHT, fill=tk.Y)
users.pack_propagate(False)
users_header = tk.Label(users, text="EN LIGNE", bg=WHITE, fg=BLACK, font=HEAD_FONT)
users_header.pack(anchor=tk.W, padx=14, pady=(12, 8))

legend = tk.Frame(users, bg=WHITE)
legend.pack(side=tk.BOTTOM, fill=tk.X, pady=12)
for txt, col in (("USER", WHITE), ("MODO", YELLOW), ("ADMIN", PINK)):
    tk.Label(legend, text=txt, bg=col, fg=BLACK, font=("Segoe UI", 7, "bold"),
             padx=4, highlightbackground=BLACK, highlightthickness=2).pack(
        side=tk.LEFT, padx=4)

users_list = tk.Frame(users, bg=WHITE)
users_list.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(0, 4))

# Colonne centre : onglets + chat + saisie
center = tk.Frame(content, bg=BG)
center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=14)

tabbar = tk.Frame(center, bg=BG)
tabbar.pack(side=tk.TOP, fill=tk.X, pady=(0, 10))

bar = tk.Frame(center, bg=BG)
bar.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
field = tk.Frame(bar, bg=WHITE, highlightbackground=BLACK, highlightthickness=3)
field.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
entry = tk.Entry(field, bg=WHITE, fg=GREY, insertbackground=BLACK,
                 font=("Segoe UI", 11), borderwidth=0, highlightthickness=0)
entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=10, padx=12)
entry.insert(0, PLACEHOLDER)
entry.bind("<Return>", send_message)
entry.bind("<Up>", hist_up)
entry.bind("<Down>", hist_down)
entry.bind("<FocusIn>", on_entry_focus_in)
entry.bind("<FocusOut>", on_entry_focus_out)
send_btn = tk.Button(bar, text="ENVOYER", command=send_message,
                     bg=PINK, fg=BLACK, activebackground=PINK, activeforeground=BLACK,
                     borderwidth=0, relief=tk.FLAT, font=("Segoe UI", 10, "bold"),
                     padx=18, cursor="hand2", highlightbackground=BLACK,
                     highlightthickness=3)
send_btn.pack(side=tk.RIGHT, ipady=6)

canvas = tk.Canvas(center, bg=BG, highlightbackground=BLACK, highlightthickness=3)
canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
canvas.bind("<Configure>", on_canvas_resize)
canvas.bind("<Enter>", lambda e: canvas.bind_all(
    "<MouseWheel>", lambda ev: canvas.yview_scroll(int(-ev.delta / 120), "units")))
canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

render_tabs()
root.protocol("WM_DELETE_WINDOW", on_close)
root.after(300, lambda: entry.focus())
root.after(300, redraw_chat)

thread = threading.Thread(target=receive, daemon=True)
thread.start()
root.after(100, poll_queue)
root.after(400, refresh_state)

root.mainloop()
