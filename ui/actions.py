"""Icon-only action buttons with replaceable art IDs and hover labels."""
import tkinter as tk
from tkinter import ttk
import sprites


class ActionButton(ttk.Button):
    def __init__(self,parent,key,glyph,label,**kwargs):
        self.label=label;self.glyph=glyph;self.tip=None
        super().__init__(parent,text=glyph,width=4,style='Action048.TButton',**kwargs)
        self.art=None if sprites.MANIFEST.get('action048_'+key,{}).get('placeholder048') else sprites.photo(self,'action048_'+key,32)
        if self.art:super().configure(image=self.art,text='')
        self.bind('<Enter>',self.show_tip);self.bind('<Leave>',self.hide_tip)
        self.bind('<ButtonPress>',self.hide_tip,add='+');self.bind('<Destroy>',self.hide_tip,add='+')
    def configure(self,cnf=None,**kwargs):
        if 'text' in kwargs:
            self.label=kwargs.pop('text');kwargs['text']='' if getattr(self,'art',None) else self.glyph
        return super().configure(cnf,**kwargs)
    config=configure
    def show_tip(self,event=None):
        self.hide_tip();self.tip=tk.Toplevel(self);self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f'+{self.winfo_rootx()}+{self.winfo_rooty()-30}')
        tk.Label(self.tip,text=self.label,bg='#172a32',fg='#e4f3f7',padx=7,pady=4).pack()
    def hide_tip(self,event=None):
        if self.tip:
            self.tip.destroy();self.tip=None


def styles(root):
    style=ttk.Style(root)
    style.configure('Action048.TButton',padding=8,font=('Segoe UI',18))
    style.configure('RouteReady048.TButton',padding=8,font=('Segoe UI',18),background='#377d58')
    style.map('RouteReady048.TButton',background=[('active','#4eaa77'),('!disabled','#377d58')])
