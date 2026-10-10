"""Editor for reusable, composable consumable definitions."""
import copy
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox
from event_editor import ArtDialog
import game.systems.consumables as rules
import sprites


class ConsumablePanel(ttk.Frame):
    def __init__(self,parent,store,on_save):
        super().__init__(parent,padding=12)
        self.store=store;self.current=None;self.variables={};self.widgets={};self.loading=False;self.image=None
        left=ttk.Frame(self);left.pack(side='left',fill='y',padx=(0,20))
        self.list=tk.Listbox(left,width=32,exportselection=False);self.list.pack(fill='both',expand=True)
        self.list.bind('<<ListboxSelect>>',self.select)
        self.copy_button=ttk.Button(left,text='Створити копію',command=self.add);self.copy_button.pack(fill='x')
        ttk.Button(left,text='Зберегти все',command=on_save).pack(fill='x')
        right=ttk.Frame(self);right.pack(fill='both',expand=True)
        self.preview=tk.Canvas(right,height=238,bg='#17251f',highlightthickness=0)
        self.title_font=tkfont.Font(self,font=('Segoe UI',19,'bold'))
        self.preview.pack(fill='x',pady=(0,10));self.preview.bind('<Configure>',lambda e:self.refresh_preview())
        form=ttk.Frame(right);form.pack(fill='both',expand=True)
        fields=[('name','Назва'),('description','Опис'),('kind','Тип'),('sprite_id','Арт')]+[(k,v[0]) for k,v in rules.FIELDS.items()]
        for n,(key,label) in enumerate(fields):
            column=(n//9)*2;row=n%9
            ttk.Label(form,text=label).grid(row=row*2,column=column,sticky='w',pady=(8,0))
            var=tk.StringVar();self.variables[key]=var
            widget=ttk.Combobox(form,textvariable=var,values=list(rules.KINDS.values()),state='readonly') if key=='kind' else ttk.Entry(form,textvariable=var,width=30)
            self.widgets[key]=widget
            var.trace_add('write',lambda *args:self.refresh_preview())
            widget.grid(row=row*2+1,column=column,sticky='ew',padx=(0,18))
            if key=='sprite_id':ttk.Button(form,text='Обрати арт',command=self.choose_art).grid(row=row*2+1,column=column+1)
        self.status=tk.StringVar();ttk.Label(form,textvariable=self.status,wraplength=600).grid(row=20,column=0,columnspan=4,sticky='w',pady=20)
        self.rebuild();self.open(self.ids[0])

    def rebuild(self):
        self.ids=[k for k,v in self.store.data['consumables'].items() if v['kind'] in rules.EDITOR_KINDS]
        self.list.delete(0,'end')
        for k in self.ids:self.list.insert('end',self.store.data['consumables'][k]['name'])
        if self.current in self.ids:self.list.selection_set(self.ids.index(self.current))

    def open(self,ident):
        self.loading=True;self.current=ident;data=self.store.data['consumables'][ident]
        for key,var in self.variables.items():var.set(str(data.get(key,rules.DEFAULTS.get(key,''))))
        self.variables['kind'].set(rules.EDITOR_KINDS[data['kind']])
        credit=data['kind']=='credits'
        for key,widget in self.widgets.items():widget.configure(state='disabled' if credit and (key in rules.FIELDS or key=='kind') else 'readonly' if key=='kind' else 'normal')
        self.copy_button.configure(state='disabled' if credit else 'normal')
        self.status.set('ID: '+ident+' · '+('Для кредитів редагуються назва, опис і арт.' if credit else 'Ефекти поєднуються. Зміни діють після перезапуску гри.'))
        self.list.selection_clear(0,'end');self.list.selection_set(self.ids.index(ident))
        self.loading=False;self.refresh_preview()

    def refresh_preview(self):
        if self.loading or not self.current:return
        c=self.preview;c.delete('all');width=max(600,c.winfo_width());x=246
        c.create_rectangle(16,16,222,222,fill='#21362b',outline='#405747')
        self.image=sprites.photo(self.winfo_toplevel(),self.variables['sprite_id'].get(),192)
        if self.image:c.create_image(119,119,image=self.image)
        elif self.current=='item_credits':
            from visuals import icon
            icon(c,dict(kind='credits',name='Кредити',rarity=0),47,47,144)
        else:
            c.create_text(119,108,text='◇',fill='#8fae98',font=('Segoe UI',40))
            c.create_text(119,155,text='Оберіть арт',fill='#9cb2a1',font=('Segoe UI',11))
        c.create_text(x,20,text=self.variables['kind'].get().upper(),anchor='nw',fill='#93b89e',font=('Segoe UI',9,'bold'))
        name=self.variables['name'].get() or 'Новий предмет';title=name
        while len(title)>1 and self.title_font.measure(title)>width-x-24:title=title[:-1]
        if title!=name:title=title[:-1]+'…'
        c.create_text(x,45,text=title,anchor='nw',fill='#f0ebd8',font=self.title_font)
        credit=self.current=='item_credits'
        summary='Валюта · Стакується · Без ваги' if credit else f"Ціна: {self.variables['value'].get()} кр.   ·   Вага: {self.variables['weight'].get()} кг   ·   ОД: {self.variables['ap_cost'].get()}"
        c.create_text(x,109,text=summary,anchor='nw',fill='#dfc382',font=('Segoe UI',10),width=width-x-24)
        effects=[]
        for key,(label,_,_) in rules.FIELDS.items():
            if key in ('value','weight','ap_cost'):continue
            try:
                if float(self.variables[key].get()):effects.append(label+': '+self.variables[key].get())
            except ValueError:pass
        detail='Зберігайте у сховку, щоб не втратити після загибелі.' if credit else '\n'.join(effects[:2]+([f'Ще ефектів: {len(effects)-2}'] if len(effects)>2 else [])) or 'Немає активних ефектів'
        c.create_text(x,143,text=detail,anchor='nw',fill='#b2d5bd',font=('Segoe UI',10),width=width-x-24)
        description=self.variables['description'].get()
        if description:c.create_text(x,204,text=description[:95]+('…' if len(description)>95 else ''),anchor='nw',fill='#9eafa4',font=('Segoe UI',9),width=width-x-24)

    def select(self,event=None):
        selected=self.list.curselection()
        if not selected:return
        ident=self.ids[selected[0]]
        if ident==self.current:return
        if self.commit():self.open(ident)
        else:self.list.selection_clear(0,'end');self.list.selection_set(self.ids.index(self.current))

    def commit(self):
        if self.current is None:return True
        try:
            data=copy.deepcopy(self.store.data['consumables'][self.current])
            for key,var in self.variables.items():
                if self.current=='item_credits' and key not in ('name','description','sprite_id'):continue
                data[key]=next(k for k,v in rules.EDITOR_KINDS.items() if v==var.get()) if key=='kind' else (float(var.get()) if key in ('weight','heal_percent') else int(var.get())) if key in rules.FIELDS else var.get().strip()
            errors=rules.validate({self.current:data},self.store.art)
            if errors:raise ValueError('\n'.join(errors))
            self.store.data['consumables'][self.current]=data
            return True
        except ValueError as exc:
            messagebox.showerror('Некоректний предмет',str(exc),parent=self.winfo_toplevel());return False

    def add(self):
        if self.current=='item_credits':return
        if not self.commit():return
        n=1
        while f'item_custom_{n:03}' in self.store.data['consumables']:n+=1
        ident=f'item_custom_{n:03}';data=copy.deepcopy(self.store.data['consumables'][self.current]);data['name']+=' — копія'
        self.store.data['consumables'][ident]=data;self.current=ident;self.rebuild();self.open(ident)

    def choose_art(self):
        value=ArtDialog(self.winfo_toplevel(),self.variables['sprite_id'].get()).show()
        if value:self.variables['sprite_id'].set(value)
