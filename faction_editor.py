"""Faction membership/relations and human templates in the shared content editor."""
import copy
import random
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from event_editor import row as compact_row, ArtDialog
import faction_rules as rules
import sprites

RELATIONS={'friendly':'Друзі','hostile':'Вороги'}

def row(parent,label,variable,values=None,readonly=False):
    widget=compact_row(parent,label,variable,values,readonly)
    widget.master.winfo_children()[0].configure(width=42,wraplength=280)
    return widget


class CatalogPanel(ttk.Frame):
    def __init__(self,parent,store,group,save):
        super().__init__(parent);self.store=store;self.group=group;self.current=None;self.loading=False;self.root=self.winfo_toplevel()
        bar=ttk.Frame(self);bar.pack(fill='x',padx=8,pady=6)
        ttk.Button(bar,text='+ Додати',command=self.add).pack(side='left')
        ttk.Button(bar,text='Зберегти все',command=save).pack(side='right')
        self.status=tk.StringVar();ttk.Label(self,textvariable=self.status).pack(side='bottom',fill='x')
        split=ttk.Panedwindow(self,orient='horizontal');split.pack(fill='both',expand=True)
        left=ttk.Frame(split);split.add(left,weight=1)
        self.list=ttk.Treeview(left,show='tree',selectmode='browse');self.list.pack(fill='both',expand=True)
        self.list.bind('<<TreeviewSelect>>',self.select)
        right=ttk.Frame(split);split.add(right,weight=3)
        canvas=tk.Canvas(right,highlightthickness=0);scroll=ttk.Scrollbar(right,command=canvas.yview)
        scroll.pack(side='right',fill='y');canvas.pack(fill='both',expand=True);canvas.configure(yscrollcommand=scroll.set)
        self.form=ttk.Frame(canvas,padding=10);window=canvas.create_window(0,0,window=self.form,anchor='nw')
        self.form.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(window,width=e.width))
        self.ident=tk.StringVar();row(self.form,'ID',self.ident,readonly=True)
        self.name=tk.StringVar();row(self.form,'Назва',self.name)

    @property
    def entries(self):return self.store.data['factions'][self.group]

    def rebuild(self):
        self.loading=True
        self.list.delete(*self.list.get_children())
        for ident,d in sorted(self.entries.items(),key=lambda pair:(pair[1].get('min_level',0),pair[1]['name'].casefold())):
            self.list.insert('','end',iid=ident,text=(f"L{d['min_level']} · " if 'min_level' in d else '')+d['name'])
        if self.current in self.entries:self.list.selection_set(self.current)
        self.loading=False

    def select(self,event=None):
        selection=self.list.selection()
        if self.loading or not selection or selection[0]==self.current:return
        if not self.commit():
            if self.current:self.list.selection_set(self.current)
            return
        self.open(selection[0])

    def commit(self):
        if not self.current:return True
        try:
            doc=copy.deepcopy(self.store.data['factions']);value=self.read()
            doc[self.group][self.current]=value
            if self.group=='factions':
                for other,relation in value['relations'].items():doc['factions'][other]['relations'][self.current]=relation
            errors=rules.validate(doc,self.store.data['monsters'],self.store.art)
            if errors:raise ValueError('\n'.join(errors))
            self.store.data['factions']=doc
            return True
        except (ValueError,KeyError) as exc:
            messagebox.showerror('Некоректні налаштування',str(exc),parent=self.root);return False

    def add(self):
        if not self.commit():return
        name=simpledialog.askstring('Новий запис','Назва:',parent=self.root)
        if not name or not name.strip():return
        prefix='human' if self.group=='humans' else 'faction';n=1
        while f'{prefix}_custom_{n:03}' in self.entries:n+=1
        ident=f'{prefix}_custom_{n:03}'
        if self.group=='humans':value=copy.deepcopy(self.entries[self.current]) if self.current else rules.human_defaults()['human_bandit']
        else:
            value=dict(name=name,player='hostile',members=[],relations={k:'hostile' for k in self.entries})
            value['relations'][ident]='friendly'
            for d in self.entries.values():d['relations'][ident]='hostile'
        value['name']=name.strip();self.entries[ident]=value;self.open(ident);self.rebuild()
        self.status.set('Додано. Для появи людини у грі призначте її до фракції.' if self.group=='humans' else 'Оберіть істот і відносини.')


class HumanPanel(CatalogPanel):
    FIELDS=[('min_level','Мінімальний рівень',1,10000),('hp','Базове HP',1,1000000),('hp_per_level','HP за рівень',0,100000),
            ('attack','Базова атака (додатково до зброї)',0,10000),('defense','Базовий захист (додатково до броні)',0,10000),
            ('speed','Кроків за хід',1,50),('regen','Регенерація HP за хід',0,100000),
            ('max_rarity','Максимальна рідкість: 0–4',0,4),('module_chance','Шанс модуля в кожному слоті, %',0,100)]
    def __init__(self,parent,store,save):
        super().__init__(parent,store,'humans',save)
        self.description=tk.StringVar();row(self.form,'Опис',self.description)
        self.art={};self.pictures={};self.images={};arts=ttk.Frame(self.form);arts.pack(fill='x')
        for field,label in [('sprite_id','Персонаж'),('corpse_sprite_id','Тіло')]:
            frame=ttk.Frame(arts);frame.pack(side='left',padx=16)
            ttk.Label(frame,text=label).pack();self.art[field]=tk.StringVar()
            self.pictures[field]=ttk.Label(frame);self.pictures[field].pack()
            ttk.Button(frame,text='Обрати арт',command=lambda k=field:self.choose_art(k)).pack()
            ttk.Button(frame,text='Стандартний вигляд',command=lambda k=field:self.clear_art(k)).pack()
        ttk.Label(self.form,text='Без арту: силует героя. Трофеїв немає. Зброя, броня та шолом генеруються з каталогів; рівень не вищий за локацію. У 50% людей бронежилет відсутній.',wraplength=700).pack(pady=6)
        self.fields={}
        for key,label,low,high in self.FIELDS:
            var=tk.StringVar();self.fields[key]=var;row(self.form,label,var)
            var.trace_add('write',lambda *args:self.refresh_preview())
        self.level=tk.StringVar(value='1');row(self.form,'Рівень для перегляду',self.level)
        self.level.trace_add('write',lambda *args:self.refresh_preview())
        self.preview=tk.StringVar();ttk.Label(self.form,textvariable=self.preview,wraplength=780,justify='left').pack(fill='x',pady=12)
        self.rebuild()
        if self.entries:self.open(next(iter(self.entries)))

    def open(self,ident):
        self.loading=True;self.current=ident;d=self.entries[ident];self.ident.set(ident);self.name.set(d['name']);self.description.set(d['description'])
        for key,var in self.fields.items():var.set(str(d[key]))
        for key,var in self.art.items():var.set(d[key])
        self.level.set(str(d['min_level']));self.loading=False;self.show_art();self.refresh_preview()

    def read(self):
        d=copy.deepcopy(self.entries[self.current]);d.update(name=self.name.get().strip(),description=self.description.get())
        for key,label,low,high in self.FIELDS:
            try:d[key]=int(self.fields[key].get())
            except ValueError:raise ValueError(label+': потрібне ціле число.')
            if not low<=d[key]<=high:raise ValueError(f'{label}: від {low} до {high}.')
        d.update({key:var.get() for key,var in self.art.items()});return d

    def choose_art(self,key):
        value=ArtDialog(self.root,self.art[key].get()).show()
        if value is not None:self.art[key].set(value);self.show_art()

    def clear_art(self,key):self.art[key].set('');self.show_art()

    def show_art(self):
        for key,var in self.art.items():
            self.images[key]=sprites.photo(self.root,var.get(),96)
            self.pictures[key].configure(image=self.images[key] or '',text='' if self.images[key] else 'Стандартний вигляд')

    def refresh_preview(self):
        if self.loading or not self.current:return
        try:
            d=self.read();level=int(self.level.get())
            if not 1<=level<=10000:raise ValueError('Рівень перегляду: 1–10000.')
            doc=copy.deepcopy(self.store.data['factions']);doc['humans'][self.current]=d
            e=rules.make_human(random.Random(47),self.current,'bandits',level,[0,0],doc)
            text=f"Приклад спорядження · L{level}: HP {e['max_hp']}, атака {e['attack']}, захист {e['defense']}, шкода зброї {e['damage']}, дальність {e['range']}\n"
            text+='\n'.join(f"{i['name']} · L{i['level']} · модулів: {len(i.get('modules',[]))}" for i in e['equipment'].values())
            if level<d['min_level']:text+='\nНа цьому рівні персонаж ще не з’являється.'
            self.preview.set(text+'\nСпорядження випадкове; це приклад, а не фіксований набір.')
        except (ValueError,KeyError) as exc:self.preview.set(str(exc))


class FactionPanel(CatalogPanel):
    def __init__(self,parent,store,save):
        super().__init__(parent,store,'factions',save)
        self.weight=tk.StringVar(value='25');row(self.form,'Шанс появи (відносна вага)',self.weight)
        ttk.Label(self.form,text='20% зустрічей — щонайменше дві різні фракції. Решта 80% — одна фракція: її вага / суму ваг доступних фракцій. Вага також впливає на вибір у змішаній групі. 0 — вимкнути появу. За чотирьох однакових ваг: по 20% усіх зустрічей на кожну окрему фракцію та 20% змішаних. Потрібні щонайменше дві доступні фракції з вагою > 0.',wraplength=720,justify='left').pack(fill='x',pady=8)
        self.player=tk.StringVar();row(self.form,'Відносини з гравцем',self.player,list(RELATIONS.values()))
        ttk.Label(self.form,text='Відносини взаємні. «Вороги» для своєї фракції означає, що її представники атакують одне одного.',wraplength=720).pack(pady=8)
        self.relation_box=ttk.LabelFrame(self.form,text='Відносини між фракціями');self.relation_box.pack(fill='x',pady=6)
        self.member_box=ttk.LabelFrame(self.form,text='Істоти, які можуть належати до фракції');self.member_box.pack(fill='x',pady=6)
        self.relations={};self.members={};self.rebuild()
        if self.entries:self.open(next(iter(self.entries)))

    def open(self,ident):
        self.current=ident;d=self.entries[ident];self.ident.set(ident);self.name.set(d['name']);self.player.set(RELATIONS[d['player']])
        self.weight.set(str(rules.encounter_weight(d)))
        self.refresh_choices()

    def refresh_choices(self):
        if not self.current:return
        d=self.entries[self.current]
        old_relations={k:v.get() for k,v in self.relations.items()} if getattr(self,'choices_for',None)==self.current else {}
        old_members={k:v.get() for k,v in self.members.items()} if getattr(self,'choices_for',None)==self.current else {}
        for frame in (self.relation_box,self.member_box):
            for widget in frame.winfo_children():widget.destroy()
        self.relations={};self.members={};self.choices_for=self.current
        for key,other in self.entries.items():
            var=tk.StringVar(value=old_relations.get(key,RELATIONS[d['relations'][key]]));self.relations[key]=var
            row(self.relation_box,other['name']+(' (між своїми)' if key==self.current else ''),var,list(RELATIONS.values()))
        choices=[(k,'Людина: '+v['name']) for k,v in self.store.data['factions']['humans'].items()]
        choices += [(k,'Монстр: '+self.store.data['texts'].get(k+'.name',k)) for k in self.store.data['monsters']]
        for key,label in choices:
            var=tk.BooleanVar(value=old_members.get(key,key in d['members']));self.members[key]=var
            ttk.Checkbutton(self.member_box,text=label,variable=var).pack(anchor='w',padx=8)

    def read(self):
        try:weight=float(self.weight.get().strip().replace(',','.'))
        except ValueError:raise ValueError('Вага появи: потрібне число від 0 до 1000000.')
        return dict(name=self.name.get().strip(),encounter_weight=weight,player=next(k for k,v in RELATIONS.items() if v==self.player.get()),
                    members=[k for k,v in self.members.items() if v.get()],
                    relations={key:next(k for k,v in RELATIONS.items() if v==var.get()) for key,var in self.relations.items()})
