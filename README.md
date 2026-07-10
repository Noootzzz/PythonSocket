# PythonSocket

Petit projet de chat en Python avec serveur, client console et client graphique.

## Lancer le projet

1. Installer Python 3.
2. Ouvrir un terminal dans le dossier du projet.
3. Lancer l'interface principale :

```bash
python launcher.py
```

Depuis cette fenetre, on peut demarrer le serveur puis ouvrir un ou plusieurs clients.

Les rooms sont des salons de discussion. On peut les rejoindre ou en creer un avec `/join <salon>`, puis revenir au salon general avec `/leave`.

Dans l'interface graphique, on voit les rooms a gauche, les membres a droite et le chat au centre. En cliquant sur une room, on la rejoint. Les commandes sont aussi affichees dans l'interface, et en cliquant dessus elles se remplissent automatiquement dans la zone de message.

## Fichiers utiles

- `launcher.py` : lance le serveur et ouvre le client graphique.
- `serveur.py` : serveur du chat.
- `client_gui.py` : client graphique principal.
- `client.py` : client en ligne de commande.
- `user_data.json` : sauvegarde des utilisateurs et des roles.

## Commandes principales

### Cote client

- `/rename <pseudo>` : changer de pseudo.
- `/mp <pseudo> <message>` : message prive.
- `/role` : voir son role.
- `/time` : heure du serveur.
- `/ping` : latence.
- `/clear` : vider l'ecran.
- `/quit` : quitter.
- `/join <salon>` : rejoindre ou creer un salon.
- `/leave` : revenir au salon general.

### Moderation

- `/kick <pseudo>` : expulser.
- `/mute <pseudo>` / `/unmute <pseudo>` : couper / retablir le chat.
- `/ban <pseudo>` / `/unban <pseudo>` : bannir / debannir.
- `/setModo <pseudo>` / `/remModo <pseudo>` : gerer les moderateurs.
- `/setAdmin <pseudo>` / `/remAdmin <pseudo>` : gerer les admins.

## Roles

- `user` : utilisateur normal.
- `moderateur` : peut kick, mute et unmute.
- `admin` : peut aussi bannir et gerer les roles.
