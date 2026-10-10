"""Local metro quest dialogue reusing standard icons and modal windows."""
import tkinter as tk
from tkinter import ttk
from visuals import PANEL,TEXT,GOLD,icon
from i18n import t as tr

def show(app,ident):
    """Display full current-stage instructions and the local interaction button."""
    g=app.game;q=g.metro_parent(ident)
    if not q or q not in g.metro_local():return
    win=app.popup(tr('metro035.dialog'),'680x650')
    tk.Label(win,text=q['title'],bg=PANEL,fg=GOLD,font=('Segoe UI',14,'bold')).pack(pady=10)
    text=tk.Text(win,bg=PANEL,fg=TEXT,wrap='word',height=18,relief='flat',font=('Segoe UI',10))
    text.pack(fill='both',expand=True,padx=18);text.insert('1.0',g.quest_text(q));text.configure(state='disabled')
    art=tk.Canvas(win,bg=PANEL,height=70,highlightthickness=0);art.pack(fill='x',padx=18)
    for n,item in enumerate(g.quest_item_views(q)):icon(art,item,10+n*80,3,64)
    def act():
        """Close the dialogue before dispatching a puzzle or dungeon request."""
        win.close_dialog();app.act(lambda:g.metro_action(ident))
    ttk.Button(win,text=tr('metro035.act'),command=act).pack(pady=10)
