######################################################################################
# client_gui.py
######################################################################################

import socket
import threading
import queue
import time
import sys
import re
import tkinter as tk
from tkinter import messagebox

SERVER = socket.gethostbyname(socket.gethostname())
PORT = 5000
ADDR = (SERVER, PORT)
FORMAT = 'utf-8'
DISCONNECT_MESSAGE = "/quit"
USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]{3,20}$")

BG = "#0f1115"
SURFACE = "#171a21"
BORDER = "#232833"
TEXT = "#e6e6e6"
MUTED = "#6b7280"
ACCENT = "#7aa2f7"
PLACEHOLDER = "Écris un message…"

TAGS = {
    "server": {"foreground": MUTED, "font": ("Segoe UI", 10, "italic")},
    "mp": {"foreground": "#bb9af7"},
    "normal": {"foreground": "#c8d0dc"},
    "me": {"foreground": "#9ece6a"},
    "info": {"foreground": MUTED},
}

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

ROOM_RE = re.compile(r"salon '([^']+)'")
ROLE_RE = re.compile(r"rôle(?: est maintenant)?\s*:\s*(\w+)")
ROLE_DISPLAY = {"user": "user", "moderateur": "modo", "admin": "admin"}
ROLE_COLORS = {"user": MUTED, "moderateur": "#e0af68", "admin": "#f7768e"}

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
running = True
ping_time = None
last_reason = None
msg_queue = queue.Queue()


def receive():
    while running:
        try:
            data = client.recv(1024)
        except OSError:
            break
        if not data:
            break
        msg_queue.put(data.decode(FORMAT, errors="replace"))
    msg_queue.put(None)


def tag_for(line):
    if line.startswith("[SERVER]") or line.startswith("Bienvenue") or line.startswith("Déconnecté"):
        return "server"
    if "[MP" in line:
        return "mp"
    return "normal"


def display(line, tag="normal"):
    chat.config(state=tk.NORMAL)
    chat.insert(tk.END, line + "\n", tag)
    chat.see(tk.END)
    chat.config(state=tk.DISABLED)


def update_meta(line):
    room = ROOM_RE.search(line)
    if room:
        room_label.config(text=f"# {room.group(1)}")
    role = ROLE_RE.search(line)
    if role:
        value = role.group(1)
        role_label.config(text=ROLE_DISPLAY.get(value, value),
                          fg=ROLE_COLORS.get(value, MUTED))


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
            display(f"Ping : {latency:.0f} ms", "info")
        else:
            update_meta(item)
            track_reason(item)
            display(item, tag_for(item))
    if running:
        root.after(100, poll_queue)


def entry_text():
    value = entry.get()
    if value == PLACEHOLDER:
        return ""
    return value.strip()


def clear_placeholder():
    if entry.get() == PLACEHOLDER:
        entry.delete(0, tk.END)
        entry.config(fg=TEXT)


def send_message(event=None):
    global ping_time
    message = entry_text()
    if not message:
        return
    entry.delete(0, tk.END)

    if message == "/clear":
        chat.config(state=tk.NORMAL)
        chat.delete(1.0, tk.END)
        chat.config(state=tk.DISABLED)
        return

    if message == "/ping":
        ping_time = time.time()

    try:
        client.sendall(message.encode(FORMAT))
    except OSError:
        display("Erreur : impossible d'envoyer.", "server")
        return

    if not message.startswith("/"):
        display(message, "me")

    if message == DISCONNECT_MESSAGE:
        on_close()


def on_close():
    global running
    if running:
        running = False
        try:
            client.sendall(DISCONNECT_MESSAGE.encode(FORMAT))
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
        entry.config(fg=MUTED)


def insert_command(event):
    idx = panel.index(f"@{event.x},{event.y}")
    line = panel.get(f"{idx} linestart", f"{idx} lineend").strip()
    if not line:
        return
    token = line.split()[0]
    if token.startswith("/"):
        entry.focus()
        clear_placeholder()
        entry.delete(0, tk.END)
        entry.insert(0, token + " ")
        entry.icursor(tk.END)


# ----- Écran de connexion -----
def ask_username():
    win = tk.Toplevel(root)
    win.title("Connexion")
    win.configure(bg=BG)
    win.resizable(False, False)
    w, h = 360, 250
    x = (win.winfo_screenwidth() // 2) - (w // 2)
    y = (win.winfo_screenheight() // 2) - (h // 2)
    win.geometry(f"{w}x{h}+{x}+{y}")

    result = {"name": None}

    tk.Label(win, text="Bienvenue 👋", bg=BG, fg=TEXT,
             font=("Segoe UI Semibold", 16)).pack(pady=(30, 4))
    tk.Label(win, text="Choisis ton pseudo", bg=BG, fg=MUTED,
             font=("Segoe UI", 10)).pack()

    field = tk.Frame(win, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
    field.pack(fill=tk.X, padx=30, pady=(18, 6))
    box = tk.Entry(field, bg=SURFACE, fg=TEXT, insertbackground=TEXT,
                   font=("Segoe UI", 12), borderwidth=0, highlightthickness=0,
                   justify=tk.CENTER)
    box.pack(fill=tk.X, ipady=9, padx=10)
    box.focus()

    hint = tk.Label(win, text="3 à 20 caractères : lettres, chiffres, _ ou -",
                    bg=BG, fg=MUTED, font=("Segoe UI", 8))
    hint.pack()

    def submit(event=None):
        value = box.get().strip()
        if not USERNAME_RE.match(value):
            hint.config(text="Pseudo invalide (3-20 : lettres, chiffres, _ ou -)", fg="#f7768e")
            return
        result["name"] = value
        win.destroy()

    box.bind("<Return>", submit)
    tk.Button(win, text="Rejoindre le chat", command=submit,
              bg=ACCENT, fg=BG, activebackground="#93b4ff", activeforeground=BG,
              borderwidth=0, relief=tk.FLAT, font=("Segoe UI Semibold", 11),
              cursor="hand2").pack(fill=tk.X, padx=30, pady=16, ipady=9)

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
    client.sendall(name.encode(FORMAT))
except OSError as e:
    messagebox.showerror("Connexion", f"Impossible de se connecter au serveur.\n{e}")
    root.destroy()
    sys.exit()

# ----- Fenêtre principale -----
root.deiconify()
root.title("Chat")
root.geometry("820x540")
root.minsize(660, 420)
root.configure(bg=BG)

header = tk.Frame(root, bg=BG)
header.pack(side=tk.TOP, fill=tk.X, padx=20, pady=(16, 8))
tk.Label(header, text="Chat", bg=BG, fg=TEXT,
         font=("Segoe UI Semibold", 14)).pack(side=tk.LEFT)

tk.Label(header, text=f"● {name}", bg=BG, fg=ACCENT,
         font=("Segoe UI", 10)).pack(side=tk.RIGHT, padx=(12, 0))
role_label = tk.Label(header, text="user", bg=SURFACE, fg=MUTED,
                      font=("Segoe UI Semibold", 9), padx=8, pady=2)
role_label.pack(side=tk.RIGHT, padx=(8, 0))
room_label = tk.Label(header, text="# general", bg=SURFACE, fg=ACCENT,
                      font=("Segoe UI Semibold", 9), padx=8, pady=2)
room_label.pack(side=tk.RIGHT)

tk.Frame(root, bg=BORDER, height=1).pack(side=tk.TOP, fill=tk.X, padx=20)

content = tk.Frame(root, bg=BG)
content.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

# Panneau des commandes (gauche)
sidebar = tk.Frame(content, bg=SURFACE, width=230)
sidebar.pack(side=tk.LEFT, fill=tk.Y)
sidebar.pack_propagate(False)

tk.Label(sidebar, text="Commandes", bg=SURFACE, fg=TEXT,
         font=("Segoe UI Semibold", 11)).pack(anchor=tk.W, padx=16, pady=(14, 6))

panel = tk.Text(sidebar, bg=SURFACE, fg=TEXT, borderwidth=0, highlightthickness=0,
                wrap=tk.NONE, cursor="arrow", padx=14, pady=4, width=1)
panel.pack(fill=tk.BOTH, expand=True)
panel.tag_config("sec", foreground=MUTED, font=("Segoe UI Semibold", 9), spacing1=8)
panel.tag_config("cmd", foreground=ACCENT, font=("Consolas", 10))
panel.tag_config("desc", foreground=MUTED, font=("Segoe UI", 8), spacing3=4)
panel.tag_config("modo", foreground="#e0af68", font=("Segoe UI Semibold", 8))
panel.tag_config("admin", foreground="#f7768e", font=("Segoe UI Semibold", 8))
panel.tag_bind("cmd", "<Button-1>", insert_command)
panel.tag_bind("cmd", "<Enter>", lambda e: panel.config(cursor="hand2"))
panel.tag_bind("cmd", "<Leave>", lambda e: panel.config(cursor="arrow"))
panel.bind("<MouseWheel>", lambda e: panel.yview_scroll(int(-e.delta / 120), "units"))

for section, cmds in SECTIONS:
    panel.insert(tk.END, section + "\n", "sec")
    for cname, desc, role in cmds:
        panel.insert(tk.END, cname + "\n", "cmd")
        panel.insert(tk.END, "   " + desc, "desc")
        if role:
            panel.insert(tk.END, "  " + role, role)
        panel.insert(tk.END, "\n", "desc")
panel.config(state=tk.DISABLED)

tk.Frame(content, bg=BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y)

# Zone de chat (droite)
right = tk.Frame(content, bg=BG)
right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

bar = tk.Frame(right, bg=BG)
bar.pack(side=tk.BOTTOM, fill=tk.X, padx=16, pady=(8, 16))

field = tk.Frame(bar, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
field.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

entry = tk.Entry(field, bg=SURFACE, fg=MUTED, insertbackground=TEXT,
                 font=("Segoe UI", 11), borderwidth=0, highlightthickness=0)
entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=9, padx=12)
entry.insert(0, PLACEHOLDER)
entry.bind("<Return>", send_message)
entry.bind("<FocusIn>", on_entry_focus_in)
entry.bind("<FocusOut>", on_entry_focus_out)

send_btn = tk.Button(bar, text="Envoyer", command=send_message,
                     bg=ACCENT, fg=BG, activebackground="#93b4ff",
                     activeforeground=BG, borderwidth=0, relief=tk.FLAT,
                     font=("Segoe UI Semibold", 10), padx=18, cursor="hand2")
send_btn.pack(side=tk.RIGHT, ipady=7)

chat = tk.Text(right, bg=BG, fg=TEXT, wrap=tk.WORD, state=tk.DISABLED,
               font=("Segoe UI", 11), borderwidth=0, highlightthickness=0,
               padx=18, pady=14, spacing1=2, spacing3=6, cursor="arrow")
chat.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

for tag, opts in TAGS.items():
    chat.tag_config(tag, **opts)

root.protocol("WM_DELETE_WINDOW", on_close)
root.after(300, lambda: entry.focus())

thread = threading.Thread(target=receive, daemon=True)
thread.start()
root.after(100, poll_queue)

root.mainloop()
