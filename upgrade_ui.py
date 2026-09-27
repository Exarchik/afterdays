"""Technician upgrade preview with explicit price, stat changes and three-star limit."""
import tkinter as tk
from tkinter import ttk
from i18n import t as tr
import visuals as v
from refinement_ui import Detail,description

class UpgradePanel(tk.Frame):
    def __init__(self,parent,app,refresh_workshop):
        """Build the item grid, before/after description, red stars and upgrade button."""
        super().__init__(parent,bg=v.PANEL);self.app=app;self.refresh_workshop=refresh_workshop
        tk.Label(self,text=tr('update031.upgrade_help'),bg=v.PANEL,fg=v.TEXT,wraplength=650).pack(padx=10,pady=10)
        self.grid=v.ItemGrid(self,self.select,height=155,columns=7);self.grid.pack(fill='both',expand=True,padx=10)
        self.stars=tk.Label(self,bg=v.PANEL,fg='#ff5555',font=('Segoe UI',14,'bold'));self.stars.pack()
        self.detail=Detail(self,height=11);self.detail.pack(fill='both',expand=True,padx=10)
        self.price=tk.Label(self,bg=v.PANEL,fg=v.GOLD);self.price.pack(pady=5)
        self.button=ttk.Button(self,text=tr('update031.upgrade'),command=self.upgrade);self.button.pack(fill='x',padx=12,pady=10)
    def refresh(self):
        """Reload carried/equipped eligible categories and preserve selection where possible."""
        g=self.app.game
        self.grid.set_items([i for i in g.bag+list(g.equipped.values()) if i and i.get('kind') in ('weapon','armor','helmet','module') and not i.get('quest_id')])
        self.select(self.grid.selection)
    def select(self,ident):
        """Show exact next-level characteristics and base-price difference before payment."""
        g=self.app.game;item=g.find(ident);quote=g.upgrade_quote(ident)
        self.stars.config(text='★'*item.get('upgrades',0) if item else '')
        self.detail.config(text=__import__('workshop033').upgrade_description(item,quote[0]) if quote else description(g,item))
        self.price.config(text=tr('update031.cost',cost=quote[1],money=g.money) if quote else tr('update032.upgrade_level') if item and item.get('level',1)>=g.level else tr('update031.limit') if item else tr('update031.select'))
        self.button.config(state='normal' if quote and quote[1]<=g.money else 'disabled')
    def upgrade(self):
        """Execute the validated purchase and refresh both workshop and player inventory."""
        if self.app.game.upgrade_item(self.grid.selection):self.app.refresh()
        self.refresh_workshop()
