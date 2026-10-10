"""Direct upgrade comparisons and the technician's paid dismantling panel."""
import tkinter as tk
from tkinter import ttk
import game_dialogs as messagebox
import progression as p
import afterdays as r
from i18n import t as tr
from visuals import ItemGrid,PANEL,TEXT,GOLD

def upgrade_description(before,after):
    """Compare the selected item to its own upgrade, never to the active equipment."""
    lines=[before['name'],tr('update033.before_after')]
    def row(label,a,b,lower=False):
        tag=('[+]' if (b<a if lower else b>a) else '[-]') if a!=b else ''
        lines.append(f'{label}\t{a:g}\t{b:g} {tag}')
    row(tr('update033.level'),before.get('level',1),after.get('level',1))
    row(tr('refinement_ui.0006'),p.item_weight(before),p.item_weight(after),True)
    if 'durability' in before:row(tr('update033.condition'),p.mr.condition(before),p.mr.condition(after))
    if before['kind']=='weapon':
        import combat033
        surcharge=int(combat033.modes(before)==('aimed',))
        row(tr('update033.ap'),before['ap']+surcharge,after['ap']+surcharge,True)
    old,new=p.stats(before),p.stats(after)
    for key in dict.fromkeys([*old,*new]):row(r.STAT_NAMES.get(key,key),old.get(key,0),new.get(key,0),key=='weight_percent')
    if 'slots' in before:row(tr('update033.slots'),before['slots'],after['slots'])
    return '\n'.join(lines)

class DismantlePanel(tk.Frame):
    def __init__(self,parent,app,refresh_workshop):
        """Build a carried-equipment list and an explicit cost/material preview."""
        super().__init__(parent,bg=PANEL);self.app=app;self.refresh_workshop=refresh_workshop
        from refinement_ui import Detail
        tk.Label(self,text=tr('update033.dismantle_help'),bg=PANEL,fg=TEXT,wraplength=650).pack(padx=10,pady=10)
        self.grid=ItemGrid(self,self.select,height=180,columns=7);self.grid.pack(fill='both',expand=True,padx=10)
        self.detail=Detail(self,height=9);self.detail.pack(fill='both',expand=True,padx=10)
        self.price=tk.Label(self,bg=PANEL,fg=GOLD);self.price.pack(pady=8)
        self.button=ttk.Button(self,text=tr('update033.dismantle'),command=self.dismantle);self.button.pack(fill='x',padx=10,pady=10)
    def refresh(self):
        """Reload eligible carried items while retaining selection."""
        self.grid.set_items([i for i in self.app.game.bag if i['kind'] in ('weapon','armor','helmet') and not i.get('quest_id')]);self.select(self.grid.selection)
    def select(self,ident):
        """Show the selected item's real stats and the quoted dismantling fee."""
        from refinement_ui import description
        g=self.app.game;quote=g.dismantle_quote(ident)
        self.detail.config(text=description(g,g.find(ident)))
        self.price.config(text=tr('update033.salvage_price',qty=quote[0],cost=quote[1],money=g.money) if quote else tr('update031.select'))
        self.button.config(state='normal' if quote and quote[1]<=g.money else 'disabled')
    def dismantle(self):
        """Confirm destruction, execute the paid operation and refresh all item views."""
        if not messagebox.askyesno(tr('update033.dismantle'),self.price.cget('text'),parent=self):return
        if self.app.game.technician_dismantle(self.grid.selection):self.app.refresh()
        self.refresh_workshop()
