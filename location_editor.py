"""Assign catalog artwork to the twelve ordinary terrain variants."""
import tkinter as tk
from tkinter import ttk
from event_editor import ArtDialog
import location_rules as rules
import sprites

class LocationArtDialog(ArtDialog):
    def __init__(self,parent,current):
        super().__init__(parent,current)
        self.keys.sort(key=lambda key:(self.art[key].get('art_category')!='locations',self.art[key].get('art_label',key)))
        self.render()

class LocationsPanel(ttk.Frame):
    def __init__(self,parent,store,save):
        super().__init__(parent,padding=12);self.store=store;self.current=next(iter(rules.TYPES));self.photo=None
        bar=ttk.Frame(self);bar.pack(fill='x')
        ttk.Label(bar,text='Локації',font=('Segoe UI',18,'bold')).pack(side='left')
        ttk.Button(bar,text='Зберегти · Ctrl+S',command=save).pack(side='right')
        body=ttk.Frame(self);body.pack(fill='both',expand=True,pady=12)
        self.types=tk.Listbox(body,width=30,exportselection=False);self.types.pack(side='left',fill='y',padx=(0,16))
        for name in rules.TYPES.values():self.types.insert('end',name)
        self.types.selection_set(0);self.types.bind('<<ListboxSelect>>',self.select_type)
        right=ttk.Frame(body);right.pack(side='left',fill='both',expand=True)
        self.title=ttk.Label(right,font=('Segoe UI',13,'bold'));self.title.pack(anchor='w')
        ttk.Label(right,text='Додайте один або кілька артів із каталогу. Вони випадково призначаються клітинкам цього типу.\nКатегорія «Локації» показується першою у вікні вибору. Видалення зі списку не видаляє сам арт.',wraplength=760).pack(anchor='w',pady=10)
        self.arts=tk.Listbox(right,height=12,exportselection=False);self.arts.pack(fill='x')
        self.arts.bind('<<ListboxSelect>>',lambda e:self.show_art());self.arts.bind('<Double-Button-1>',lambda e:self.choose(True))
        buttons=ttk.Frame(right);buttons.pack(fill='x',pady=8)
        for title,command in [('+ Додати арт',lambda:self.choose(False)),('Замінити арт',lambda:self.choose(True)),('Видалити зі списку',self.remove)]:
            ttk.Button(buttons,text=title,command=command).pack(side='left',padx=(0,8))
        self.preview=ttk.Label(right);self.preview.pack(anchor='w',pady=8)
        ttk.Label(right,text='«Біля озера» / «біля гір» — сусідство по ребру гекса. Озеро має пріоритет.\nПорожній список: використовується базовий тип місцевості, потім зображення гекса.\nЗбережіть зміни та перезапустіть гру. Арт клітинки зберігається у сейві, доки є в її списку.',wraplength=760).pack(anchor='w')
        self.rebuild()

    @property
    def values(self):return self.store.data['locations'].setdefault(self.current,[])

    def select_type(self,event=None):
        selection=self.types.curselection()
        if selection:self.current=list(rules.TYPES)[selection[0]];self.rebuild()

    def rebuild(self):
        self.title.configure(text=rules.TYPES[self.current]);self.arts.delete(0,'end')
        for key in self.values:self.arts.insert('end',self.store.art.get(key,{}).get('art_label',key)+' ['+key+']')
        if self.values:self.arts.selection_set(0)
        self.show_art()

    def show_art(self):
        selected=self.arts.curselection()
        self.photo=sprites.photo(self,self.values[selected[0]],192) if selected else None
        self.preview.configure(image=self.photo or '',text='' if self.photo else 'Немає обраного арту')

    def choose(self,replace=False):
        selected=self.arts.curselection()
        if replace and not selected:return
        result=LocationArtDialog(self.winfo_toplevel(),self.values[selected[0]] if replace else '').show()
        if not result or result in self.values:return
        if replace:self.values[selected[0]]=result
        else:self.values.append(result)
        self.rebuild()

    def remove(self):
        selected=self.arts.curselection()
        if selected:self.values.pop(selected[0]);self.rebuild()
