"""Repair kits: select carried or equipped gear and preview the exact result."""
import tkinter as tk
from tkinter import ttk
from inspection_ui import window
from refinement_ui import Detail,description
from visuals import ItemGrid,PANEL,TEXT,GOLD
from i18n import t as tr
import module_rules as mr

def show(app,kit_id=None):
    g=app.game
    if g.battle:return
    app.route.pause();win=window(app,tr('scav.repair_menu'))
    info=tk.Label(win,bg=PANEL,fg=GOLD,wraplength=560);info.pack(pady=12,padx=10)
    def select(ident):
        item=g.find(ident);detail.config(text=description(g,item))
        kit=g.repair_kit(kit_id)
        usable=bool(kit and item and g.can_repair_with_kit(item))
        button.config(state='normal' if usable else 'disabled')
        preview.config(text=tr('scav.repair_preview',before=round(mr.condition(item)),after=round(min(mr.max_condition(item),mr.condition(item)+__import__('consumable_rules').definition(kit)['repair']))) if usable else tr('update033.kit_limit') if item and item['kind']=='weapon' and mr.condition(item)<=20 else '')
    win.app=app
    grid=ItemGrid(win,select,height=220,columns=6);grid.pack(fill='both',expand=True,padx=12)
    detail=Detail(win,height=8);detail.pack(fill='both',expand=True,padx=12)
    preview=tk.Label(win,bg=PANEL,fg=TEXT);preview.pack(pady=8)
    def refresh():
        info.config(text=tr('scav.kits_available',qty=g.count('repairkit')))
        grid.set_items([i for i in g.bag+list(g.equipped.values()) if i and (i['kind'] in ('weapon','armor','helmet') or i.get('quest_repair'))]);select(grid.selection)
    def repair():
        if g.repair_with_kit(grid.selection,kit_id):app.refresh()
        refresh()
    button=ttk.Button(win,text=tr('scav.use_kit'),command=repair);button.pack(fill='x',padx=12,pady=8);refresh()
