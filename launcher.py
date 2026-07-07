######################################################################################
# launcher.py
######################################################################################

import os
import sys
import subprocess
import tkinter as tk

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_SCRIPT = "serveur.py"
CLIENT_SCRIPT = "client_gui.py"

BG = "#0f1115"
SURFACE = "#171a21"
BORDER = "#232833"
TEXT = "#e6e6e6"
MUTED = "#6b7280"
ACCENT = "#7aa2f7"
DANGER = "#f7768e"
OK = "#9ece6a"

server_process = None


def gui_python():
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return pythonw if os.path.exists(pythonw) else sys.executable


def server_running():
    return server_process is not None and server_process.poll() is None


def toggle_server():
    global server_process
    if server_running():
        server_process.terminate()
        server_process = None
    else:
        server_process = subprocess.Popen([sys.executable, SERVER_SCRIPT], cwd=BASE_DIR)
    refresh()


def open_client():
    subprocess.Popen([gui_python(), CLIENT_SCRIPT], cwd=BASE_DIR)


def refresh():
    if server_running():
        status.config(text="● Serveur en marche", fg=OK)
        server_btn.config(text="Arrêter le serveur", bg=DANGER)
        client_btn.config(state=tk.NORMAL)
    else:
        status.config(text="● Serveur arrêté", fg=MUTED)
        server_btn.config(text="Démarrer le serveur", bg=SURFACE)
        client_btn.config(state=tk.DISABLED)
    root.after(700, refresh)


def on_close():
    if server_running():
        server_process.terminate()
    root.destroy()


root = tk.Tk()
root.title("Chat")
root.geometry("360x300")
root.minsize(320, 280)
root.configure(bg=BG)

tk.Label(root, text="Chat", bg=BG, fg=TEXT,
         font=("Segoe UI Semibold", 18)).pack(pady=(26, 2))

status = tk.Label(root, text="● Serveur arrêté", bg=BG, fg=MUTED,
                  font=("Segoe UI", 10))
status.pack(pady=18)

server_btn = tk.Button(root, text="Démarrer le serveur", command=toggle_server,
                       bg=SURFACE, fg=TEXT, activebackground=BORDER,
                       activeforeground=TEXT, borderwidth=0, relief=tk.FLAT,
                       font=("Segoe UI Semibold", 11), cursor="hand2")
server_btn.pack(fill=tk.X, padx=30, ipady=10)

client_btn = tk.Button(root, text="Ouvrir un client", command=open_client,
                       bg=ACCENT, fg=BG, activebackground="#93b4ff",
                       activeforeground=BG, borderwidth=0, relief=tk.FLAT,
                       font=("Segoe UI Semibold", 11), cursor="hand2",
                       state=tk.DISABLED)
client_btn.pack(fill=tk.X, padx=30, pady=12, ipady=10)


root.protocol("WM_DELETE_WINDOW", on_close)
refresh()
root.mainloop()
