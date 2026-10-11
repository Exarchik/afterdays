"""Check editor controls without saving the content catalog."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tkinter as tk
from tkinter import ttk
from event_editor import Editor,EffectDialog
root=tk.Tk();root.geometry('1100x850')
editor=Editor(root);editor.pack(fill='both',expand=True);root.update()
assert any(isinstance(w,ttk.Scrollbar) for w in editor.tree.master.winfo_children())
for effect in [dict(kind='ambush',faction='mixed',amount=4),dict(kind='ambush',faction='settlers',amount=3),dict(kind='ambush',monster_id='monster_rodent',amount=6)]:
    dialog=EffectDialog(root,effect);root.update()
    result=dialog.read()
    for key,value in effect.items():assert result[key]==value
    assert str(dialog.ambush_field.cget('state'))=='readonly'
    dialog.destroy()
root.destroy();print('PASS: event list scrollbar and ambush editor roundtrip')
