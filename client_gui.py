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

# --- Thème : SaaS clair professionnel ---
BG = "#ffffff"
SIDEBAR = "#f7f8fa"
HOVER = "#eef0f3"
BORDER = "#e6e8eb"
TEXT = "#1a1d24"
MUTED = "#6b7280"
FAINT = "#9ca3af"
ACCENT = "#5b5bd6"
ACCENT_HOVER = "#4c4cc7"
ACCENT_SOFT = "#ececfb"
PURPLE_NAME = "#8b5cf6"
GREEN = "#16a34a"
UI = "Segoe UI"
PLACEHOLDER = "Envoyer un message…"

AVATAR_COLORS = ["#5b5bd6", "#0ea5e9", "#10b981", "#f59e0b",
                 "#ef4444", "#8b5cf6", "#ec4899", "#14b8a6"]

ROOM_RE = re.compile(r"salon '([^']+)'")
ROLE_RE = re.compile(r"rôle(?: est maintenant)?\s*:\s*(\w+)")
RENAME_RE = re.compile(r"Tu es maintenant '([^']+)'")
USER_RE = re.compile(r"(\S+) \((\w+), ([^)]+)\)")
MSG_RE = re.compile(r"^\[(\d\d:\d\d)\] \[([^\]]+)\] (.*)$")
ROLE_DISPLAY = {"user": "Membre", "moderateur": "Modérateur", "admin": "Admin"}
ROLE_PILL = {"admin": (ACCENT_SOFT, ACCENT), "moderateur": ("#fef3c7", "#b45309")}

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
text_labels = []


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


def avatar_color(person):
    return AVATAR_COLORS[sum(map(ord, person)) % len(AVATAR_COLORS)] if person else ACCENT


def make_avatar(parent, person, size=36):
    av = tk.Canvas(parent, width=size, height=size, bg=parent["bg"], highlightthickness=0)
    av.create_oval(1, 1, size - 1, size - 1, fill=avatar_color(person), outline="")
    av.create_text(size / 2, size / 2, text=(person or "?")[0].upper(),
                   fill="#ffffff", font=(UI, int(size / 2.6), "bold"))
    return av


# ----- Fil de messages -----
def scroll_bottom():
    feed_canvas.update_idletasks()
    feed_canvas.yview_moveto(1.0)


def add_system(text):
    row = tk.Frame(feed, bg=BG)
    row.pack(fill=tk.X, pady=(8, 4))
    tk.Label(row, text=text, bg=BG, fg=FAINT, font=(UI, 8)).pack()
    scroll_bottom()


def add_row(person, label, text, when, mine):
    row = tk.Frame(feed, bg=BG)
    row.pack(fill=tk.X, padx=18, pady=(8, 0), anchor="w")

    make_avatar(row, person, 36).pack(side=tk.LEFT, anchor="n")

    body = tk.Frame(row, bg=BG)
    body.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(11, 0))

    head = tk.Frame(body, bg=BG)
    head.pack(fill=tk.X, anchor="w")
    if mine:
        name_color = ACCENT
    elif label.startswith("MP"):
        name_color = PURPLE_NAME
    else:
        name_color = TEXT
    tk.Label(head, text=label, bg=BG, fg=name_color,
             font=(UI, 10, "bold")).pack(side=tk.LEFT)
    tk.Label(head, text=when, bg=BG, fg=FAINT,
             font=(UI, 8)).pack(side=tk.LEFT, padx=(8, 0))

    msg = tk.Label(body, text=text, bg=BG, fg=TEXT, font=(UI, 11),
                   wraplength=520, justify=tk.LEFT, anchor="w")
    msg.pack(fill=tk.X, anchor="w")
    text_labels.append(msg)
    scroll_bottom()


def add_message(line, mine=False):
    m = MSG_RE.match(line)
    if not m:
        add_system(line)
        return
    when, who, text = m.groups()
    if mine:
        person, label = name, name
    elif who.startswith("MP à "):
        person, label = who[5:], who
    elif who.startswith("MP de "):
        person, label = who[6:], who
    else:
        person, label = who, who
    add_row(person, label, text, when, mine)


def clear_chat():
    for w in feed.winfo_children():
        w.destroy()
    text_labels.clear()


def on_feed_resize(event):
    feed_canvas.itemconfig(feed_win, width=event.width)
    w = max(event.width - 100, 220)
    for lbl in text_labels:
        try:
            lbl.config(wraplength=w)
        except tk.TclError:
            pass


# ----- Salons (liste latérale) -----
def render_rooms():
    for w in rooms_list.winfo_children():
        w.destroy()
    for room in known_rooms:
        active = room == current_room
        base = ACCENT_SOFT if active else SIDEBAR
        item = tk.Label(rooms_list, text=f"#   {room}", bg=base,
                        fg=ACCENT if active else TEXT,
                        font=(UI, 10, "bold") if active else (UI, 10),
                        anchor="w", padx=12, pady=7, cursor="hand2")
        item.pack(fill=tk.X, padx=6, pady=1)
        item.bind("<Button-1>", lambda e, r=room: switch_room(r))
        if not active:
            item.bind("<Enter>", lambda e, w=item: w.config(bg=HOVER))
            item.bind("<Leave>", lambda e, w=item: w.config(bg=SIDEBAR))
    add = tk.Label(rooms_list, text="+   Ajouter un salon", bg=SIDEBAR, fg=MUTED,
                   font=(UI, 9), anchor="w", padx=12, pady=7, cursor="hand2")
    add.pack(fill=tk.X, padx=6, pady=(2, 0))
    add.bind("<Button-1>", lambda e: create_room())
    add.bind("<Enter>", lambda e: add.config(bg=HOVER))
    add.bind("<Leave>", lambda e: add.config(bg=SIDEBAR))


def switch_room(room):
    if room != current_room:
        send_raw(f"/join {room}")


def themed_input(title, label_text, action):
    win = tk.Toplevel(root)
    win.title(title)
    win.configure(bg=BG)
    win.resizable(False, False)
    win.transient(root)
    w, h = 360, 200
    x = root.winfo_x() + (root.winfo_width() // 2) - (w // 2)
    y = root.winfo_y() + (root.winfo_height() // 2) - (h // 2)
    win.geometry(f"{w}x{h}+{max(x, 0)}+{max(y, 0)}")

    result = {"value": None}

    tk.Label(win, text=label_text, bg=BG, fg=TEXT,
             font=(UI, 12, "bold")).pack(anchor=tk.W, padx=26, pady=(24, 12))
    field = tk.Frame(win, bg=BG, highlightbackground=BORDER, highlightthickness=1)
    field.pack(fill=tk.X, padx=26)
    box = tk.Entry(field, bg=BG, fg=TEXT, insertbackground=TEXT,
                   font=(UI, 12), borderwidth=0, highlightthickness=0)
    box.pack(fill=tk.X, ipady=8, padx=10)

    def ok(event=None):
        value = box.get().strip()
        if value:
            result["value"] = value
        win.destroy()

    box.bind("<Return>", ok)
    buttons = tk.Frame(win, bg=BG)
    buttons.pack(fill=tk.X, padx=26, pady=20)
    tk.Button(buttons, text=action, command=ok, bg=ACCENT, fg="#ffffff",
              activebackground=ACCENT_HOVER, activeforeground="#ffffff", borderwidth=0,
              relief=tk.FLAT, font=(UI, 10, "bold"), cursor="hand2",
              padx=16).pack(side=tk.RIGHT, ipady=5)
    tk.Button(buttons, text="Annuler", command=win.destroy, bg=BG, fg=MUTED,
              activebackground=HOVER, activeforeground=TEXT, borderwidth=0,
              relief=tk.FLAT, font=(UI, 10), cursor="hand2",
              padx=12).pack(side=tk.RIGHT, padx=(0, 8), ipady=5)

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
    render_rooms()


# ----- Membres -----
def render_users():
    for w in users_list.winfo_children():
        w.destroy()
    users_header.config(text=f"Membres — {len(online_users)}")
    if not online_users:
        tk.Label(users_list, text="Chargement…", bg=SIDEBAR, fg=FAINT,
                 font=(UI, 9)).pack(anchor=tk.W, padx=16, pady=6)
        return
    order = {"admin": 0, "moderateur": 1, "user": 2}
    ordered = sorted(online_users, key=lambda u: (order.get(u[1], 3), u[0].lower()))
    for uname, role, room in ordered:
        row = tk.Frame(users_list, bg=SIDEBAR)
        row.pack(fill=tk.X, padx=10, pady=3)
        make_avatar(row, uname, 26).pack(side=tk.LEFT)
        tk.Label(row, text=uname, bg=SIDEBAR, fg=TEXT,
                 font=(UI, 10)).pack(side=tk.LEFT, padx=(8, 0))
        if role in ROLE_PILL:
            pbg, pfg = ROLE_PILL[role]
            tk.Label(row, text=ROLE_DISPLAY[role], bg=pbg, fg=pfg,
                     font=(UI, 7, "bold"), padx=5, pady=1).pack(side=tk.RIGHT)


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
        channel_title.config(text=f"#  {current_room}")
        if current_room not in known_rooms:
            known_rooms.append(current_room)
        render_rooms()
    role = ROLE_RE.search(line)
    if role:
        value = role.group(1)
        role_label.config(text=ROLE_DISPLAY.get(value, value))
    renamed = RENAME_RE.search(line)
    if renamed:
        name = renamed.group(1)
        pseudo_label.config(text=name)


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
        entry.config(fg=TEXT)


def set_entry(text):
    clear_placeholder()
    entry.delete(0, tk.END)
    entry.insert(0, text)
    entry.config(fg=TEXT)
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
    field.config(highlightbackground=ACCENT, highlightcolor=ACCENT)


def on_entry_focus_out(event):
    if not entry.get():
        entry.insert(0, PLACEHOLDER)
        entry.config(fg=FAINT)
    field.config(highlightbackground=BORDER, highlightcolor=BORDER)


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
    w, h = 380, 280
    x = (win.winfo_screenwidth() // 2) - (w // 2)
    y = (win.winfo_screenheight() // 2) - (h // 2)
    win.geometry(f"{w}x{h}+{x}+{y}")

    result = {"name": None}

    tk.Label(win, text="Bienvenue", bg=BG, fg=TEXT,
             font=(UI, 18, "bold")).pack(pady=(34, 2))
    tk.Label(win, text="Connecte-toi pour rejoindre la conversation", bg=BG, fg=MUTED,
             font=(UI, 10)).pack()

    field2 = tk.Frame(win, bg=BG, highlightbackground=BORDER, highlightthickness=1)
    field2.pack(fill=tk.X, padx=34, pady=(22, 6))
    box = tk.Entry(field2, bg=BG, fg=TEXT, insertbackground=TEXT,
                   font=(UI, 12), borderwidth=0, highlightthickness=0)
    box.pack(fill=tk.X, ipady=10, padx=12)
    box.focus()

    hint = tk.Label(win, text="Pseudo : 3 à 20 caractères (lettres, chiffres, _ ou -)",
                    bg=BG, fg=FAINT, font=(UI, 8))
    hint.pack()

    def submit(event=None):
        value = box.get().strip()
        if not USERNAME_RE.match(value):
            hint.config(text="Pseudo invalide : 3-20 caractères (lettres, chiffres, _ ou -)",
                        fg="#dc2626")
            return
        result["name"] = value
        win.destroy()

    box.bind("<Return>", submit)
    tk.Button(win, text="Rejoindre", command=submit,
              bg=ACCENT, fg="#ffffff", activebackground=ACCENT_HOVER, activeforeground="#ffffff",
              borderwidth=0, relief=tk.FLAT, font=(UI, 11, "bold"),
              cursor="hand2").pack(fill=tk.X, padx=34, pady=20, ipady=9)

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
root.geometry("1040x640")
root.minsize(860, 520)
root.configure(bg=BG)

content = tk.Frame(root, bg=BG)
content.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

# --- Colonne gauche : salons + commandes ---
sidebar = tk.Frame(content, bg=SIDEBAR, width=248)
sidebar.pack(side=tk.LEFT, fill=tk.Y)
sidebar.pack_propagate(False)

tk.Label(sidebar, text="Messagerie", bg=SIDEBAR, fg=TEXT,
         font=(UI, 13, "bold")).pack(anchor=tk.W, padx=18, pady=(18, 12))

tk.Label(sidebar, text="SALONS", bg=SIDEBAR, fg=FAINT,
         font=(UI, 8, "bold")).pack(anchor=tk.W, padx=18, pady=(4, 2))
rooms_list = tk.Frame(sidebar, bg=SIDEBAR)
rooms_list.pack(fill=tk.X)

tk.Label(sidebar, text="COMMANDES", bg=SIDEBAR, fg=FAINT,
         font=(UI, 8, "bold")).pack(anchor=tk.W, padx=18, pady=(16, 2))
panel = tk.Text(sidebar, bg=SIDEBAR, fg=TEXT, borderwidth=0, highlightthickness=0,
                wrap=tk.NONE, cursor="arrow", padx=14, pady=2, width=1)
panel.pack(fill=tk.BOTH, expand=True)
panel.tag_config("sec", foreground=MUTED, font=(UI, 8, "bold"), spacing1=10, spacing3=2)
panel.tag_config("cmd", foreground=ACCENT, font=("Consolas", 10))
panel.tag_config("desc", foreground=FAINT, font=(UI, 8), spacing3=4)
panel.tag_config("modo", foreground="#b45309", font=(UI, 8, "bold"))
panel.tag_config("admin", foreground=ACCENT, font=(UI, 8, "bold"))
panel.tag_bind("cmd", "<Button-1>", insert_command)
panel.tag_bind("cmd", "<Enter>", lambda e: panel.config(cursor="hand2"))
panel.tag_bind("cmd", "<Leave>", lambda e: panel.config(cursor="arrow"))
panel.bind("<MouseWheel>", lambda e: panel.yview_scroll(int(-e.delta / 120), "units"))
for section, cmds in SECTIONS:
    for cname, desc, role in cmds:
        panel.insert(tk.END, cname + "\n", "cmd")
        panel.insert(tk.END, "   " + desc, "desc")
        if role:
            panel.insert(tk.END, "  " + role, role)
        panel.insert(tk.END, "\n", "desc")
panel.config(state=tk.DISABLED)

# --- Colonne droite : membres ---
users = tk.Frame(content, bg=SIDEBAR, width=210)
users.pack(side=tk.RIGHT, fill=tk.Y)
users.pack_propagate(False)
users_header = tk.Label(users, text="Membres", bg=SIDEBAR, fg=TEXT,
                        font=(UI, 11, "bold"))
users_header.pack(anchor=tk.W, padx=16, pady=(18, 10))
users_list = tk.Frame(users, bg=SIDEBAR)
users_list.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

# --- Centre : en-tête + fil + saisie ---
center = tk.Frame(content, bg=BG)
center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

topbar = tk.Frame(center, bg=BG, height=58)
topbar.pack(side=tk.TOP, fill=tk.X)
topbar.pack_propagate(False)
channel_title = tk.Label(topbar, text="#  general", bg=BG, fg=TEXT,
                         font=(UI, 13, "bold"))
channel_title.pack(side=tk.LEFT, padx=20)

user_box = tk.Frame(topbar, bg=BG)
user_box.pack(side=tk.RIGHT, padx=16)
make_avatar(user_box, name, 30).pack(side=tk.LEFT)
id_box = tk.Frame(user_box, bg=BG)
id_box.pack(side=tk.LEFT, padx=(8, 0))
pseudo_label = tk.Label(id_box, text=name, bg=BG, fg=TEXT, font=(UI, 10, "bold"))
pseudo_label.pack(anchor=tk.W)
role_label = tk.Label(id_box, text="Membre", bg=BG, fg=MUTED, font=(UI, 8))
role_label.pack(anchor=tk.W)

tk.Frame(center, bg=BORDER, height=1).pack(side=tk.TOP, fill=tk.X)

# saisie (en bas)
bar = tk.Frame(center, bg=BG)
bar.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=(6, 18))
field = tk.Frame(bar, bg=BG, highlightbackground=BORDER, highlightthickness=1)
field.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
entry = tk.Entry(field, bg=BG, fg=FAINT, insertbackground=TEXT,
                 font=(UI, 11), borderwidth=0, highlightthickness=0)
entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=11, padx=14)
entry.insert(0, PLACEHOLDER)
entry.bind("<Return>", send_message)
entry.bind("<Up>", hist_up)
entry.bind("<Down>", hist_down)
entry.bind("<FocusIn>", on_entry_focus_in)
entry.bind("<FocusOut>", on_entry_focus_out)
send_btn = tk.Button(bar, text="Envoyer", command=send_message,
                     bg=ACCENT, fg="#ffffff", activebackground=ACCENT_HOVER,
                     activeforeground="#ffffff", borderwidth=0, relief=tk.FLAT,
                     font=(UI, 10, "bold"), padx=20, cursor="hand2")
send_btn.pack(side=tk.RIGHT, ipady=9)

# fil scrollable
feed_wrap = tk.Frame(center, bg=BG)
feed_wrap.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
feed_canvas = tk.Canvas(feed_wrap, bg=BG, highlightthickness=0)
feed_scroll = tk.Scrollbar(feed_wrap, orient=tk.VERTICAL, command=feed_canvas.yview)
feed_canvas.configure(yscrollcommand=feed_scroll.set)
feed_scroll.pack(side=tk.RIGHT, fill=tk.Y)
feed_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
feed = tk.Frame(feed_canvas, bg=BG)
feed_win = feed_canvas.create_window((0, 0), window=feed, anchor="nw")
feed.bind("<Configure>", lambda e: feed_canvas.configure(scrollregion=feed_canvas.bbox("all")))
feed_canvas.bind("<Configure>", on_feed_resize)
feed_canvas.bind("<Enter>", lambda e: feed_canvas.bind_all(
    "<MouseWheel>", lambda ev: feed_canvas.yview_scroll(int(-ev.delta / 120), "units")))
feed_canvas.bind("<Leave>", lambda e: feed_canvas.unbind_all("<MouseWheel>"))

render_rooms()
root.protocol("WM_DELETE_WINDOW", on_close)
root.after(300, lambda: entry.focus())

thread = threading.Thread(target=receive, daemon=True)
thread.start()
root.after(100, poll_queue)
root.after(400, refresh_state)

root.mainloop()
