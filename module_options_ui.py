"""Module compatibility controls shared by every module in the editor."""
import tkinter as tk
from tkinter import ttk
import entity_catalog as catalog

RARITY_COLORS=('#a8acaa','#53a9ff','#f4cd55','#c58bfa','#ff6570')


class ModuleOptions(ttk.LabelFrame):
    def __init__(self,parent,target,changed):
        super().__init__(parent,text='Сумісність модуля',padding=8)
        self.target=target;self.changed=changed
        ttk.Label(self,text='Тип спорядження').pack(anchor='w')
        ttk.Combobox(self,textvariable=target,state='readonly',values=[catalog.TARGETS[k] for k in ('weapon','protection')]).pack(fill='x',pady=4)
        self.protection=ttk.Frame(self)
        self.armor=tk.BooleanVar(value=True);self.helmet=tk.BooleanVar(value=True)
        for label,var in [('Броня',self.armor),('Шоломи',self.helmet)]:
            ttk.Checkbutton(self.protection,text=label,variable=var,command=changed).pack(side='left',padx=4)
        self.weapons=ttk.Frame(self);self.categories={}
        ttk.Label(self.weapons,text='Придатний для класів зброї:').pack(anchor='w')
        for key,label in catalog.CATEGORIES.items():
            var=tk.BooleanVar(value=True);self.categories[key]=var
            ttk.Checkbutton(self.weapons,text=label,variable=var,command=changed).pack(anchor='w')
        self.rarity_frame=ttk.Frame(self);self.rarity_frame.pack(fill='x',pady=(8,0))
        ttk.Label(self.rarity_frame,text='Мінімальна рідкість спорядження').pack(anchor='w')
        self.minimum=tk.IntVar(value=0)
        self.rarity_button=tk.Menubutton(self.rarity_frame,relief='raised',anchor='w',bg='#26332f',activebackground='#34463e')
        self.rarity_button.pack(fill='x',pady=4)
        menu=tk.Menu(self.rarity_button,tearoff=False,bg='#26332f',activebackground='#34463e')
        for i,(label,color) in enumerate(zip(catalog.RARITIES,RARITY_COLORS)):
            menu.add_radiobutton(label='● '+label,variable=self.minimum,value=i,foreground=color,activeforeground=color,selectcolor=color)
        self.rarity_button.configure(menu=menu)
        ttk.Label(self.rarity_frame,text='Рідкість самого модуля також не може перевищувати рідкість спорядження.',wraplength=340).pack(anchor='w')
        target.trace_add('write',self.update_family)
        self.minimum.trace_add('write',self.update_rarity)
        self.update_rarity();self.update_family()

    def update_family(self,*_):
        self.protection.pack_forget();self.weapons.pack_forget()
        frame=self.weapons if self.target.get()==catalog.TARGETS['weapon'] else self.protection
        frame.pack(fill='x',before=self.rarity_frame,pady=4)
        self.changed()

    def update_rarity(self,*_):
        value=self.minimum.get()
        self.rarity_button.configure(text='● '+catalog.RARITIES[value],fg=RARITY_COLORS[value],activeforeground=RARITY_COLORS[value])
        self.changed()

    def load(self,data):
        target=data.get('target','protection')
        self.target.set(catalog.TARGETS['weapon' if target=='weapon' else 'protection'])
        self.armor.set(target in ('armor','protection','weapon'))
        self.helmet.set(target in ('helmet','protection','weapon'))
        for key,var in self.categories.items():var.set(key in data.get('weapon_categories',catalog.CATEGORIES))
        self.minimum.set(data.get('min_equipment_rarity',0))

    def apply(self,data):
        if self.target.get()==catalog.TARGETS['weapon']:
            data['target']='weapon'
            categories=[key for key,var in self.categories.items() if var.get()]
            if not categories:raise ValueError('Виберіть хоча б один клас зброї для модуля.')
        else:
            armor,helmet=self.armor.get(),self.helmet.get()
            if not (armor or helmet):raise ValueError('Виберіть броню та/або шоломи для модуля.')
            data['target']='protection' if armor and helmet else 'armor' if armor else 'helmet'
            categories=[key for key,var in self.categories.items() if var.get()] or list(catalog.CATEGORIES)
        data['weapon_categories']=categories
        data['min_equipment_rarity']=self.minimum.get()
