"""Equipment, module and monster sections of the Afterdays content editor."""
import copy
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import entity_catalog as catalog
from event_editor import Dialog, ArtDialog, row
import sprites


class StatDialog(Dialog):
    def __init__(self, parent, key='damage', values=None, curve=False):
        super().__init__(parent, 'Бонуси за рідкістю' if curve else 'Постійний модифікатор', '620x420')
        self.curve=curve
        self.stat=tk.StringVar(value=catalog.STATS[key]);row(self.body,'Параметр',self.stat,list(catalog.STATS.values()))
        self.values=[]
        for label,value in zip(catalog.RARITIES if curve else ['Значення'],values or ([1]*5 if curve else [0])):
            var=tk.StringVar(value=str(value));self.values.append(var);row(self.body,label,var)
        ttk.Label(self.body,text='Числові бонуси ростуть на 6% за рівень; відсотки й атака\nне ростуть. Постійні модифікатори додаються після масштабування.',wraplength=570).pack(pady=14)
    def read(self):
        import math
        key=next(k for k,v in catalog.STATS.items() if v==self.stat.get())
        values=[float(v.get()) for v in self.values]
        if not all(math.isfinite(v) for v in values):raise ValueError('Потрібні скінченні числа.')
        return key,[int(v) if v.is_integer() else v for v in values]


class StatTable(ttk.Frame):
    def __init__(self,parent,title,changed,curve=False):
        super().__init__(parent);self.rows={};self.curve=curve;self.changed=changed
        ttk.Label(self,text=title).pack(anchor='w',pady=(12,4))
        self.list=tk.Listbox(self,height=4,exportselection=False);self.list.pack(fill='x')
        self.list.bind('<Double-1>',lambda e:self.edit())
        bar=ttk.Frame(self);bar.pack(fill='x',pady=3)
        for label,command in [('Додати',self.add),('Змінити',self.edit),('Прибрати',self.remove)]:
            ttk.Button(bar,text=label,command=command,width=10).pack(side='left',padx=2)
        if curve:ttk.Button(bar,text='↑',command=self.up,width=3).pack(side='left')
    def set(self,data):self.rows=copy.deepcopy(data);self.refresh()
    def refresh(self):
        self.list.delete(0,'end')
        for key,value in self.rows.items():
            self.list.insert('end',catalog.STATS[key]+': '+(' / '.join(map(str,value)) if self.curve else str(value)))
    def selection(self):
        return list(self.rows)[self.list.curselection()[0]] if self.list.curselection() else None
    def set_value(self,value,old=None):
        if value is None:return
        key,values=value
        if key!=old and key in self.rows:
            messagebox.showerror('Параметр уже є','Відредагуйте наявний рядок.',parent=self.winfo_toplevel());return
        if old and key!=old:del self.rows[old]
        self.rows[key]=values if self.curve else values[0];self.refresh();self.changed()
    def add(self):self.set_value(StatDialog(self.winfo_toplevel(),curve=self.curve).show())
    def edit(self):
        key=self.selection()
        if key:self.set_value(StatDialog(self.winfo_toplevel(),key,self.rows[key] if self.curve else [self.rows[key]],self.curve).show(),key)
    def remove(self):
        key=self.selection()
        if key:del self.rows[key];self.refresh();self.changed()
    def up(self):
        key=self.selection()
        if key:
            pairs=list(self.rows.items());i=list(self.rows).index(key)
            if i:pairs[i-1],pairs[i]=pairs[i],pairs[i-1];self.rows=dict(pairs);self.refresh();self.list.selection_set(i-1);self.changed()


class EntityPanel(ttk.Frame):
    def __init__(self,parent,store,section,on_save):
        super().__init__(parent,padding=10)
        self.store=store;self.section=section;self.on_save=on_save;self.current=None;self.loading=False;self.pending=None
        self.root=self.winfo_toplevel()
        bar=ttk.Frame(self);bar.pack(fill='x',pady=(0,8))
        ttk.Label(bar,text=catalog.SECTIONS[section],font=('Segoe UI',18,'bold')).pack(side='left')
        for label,command in [('Зберегти всі зміни',on_save),('Дублювати',self.duplicate),('Додати',self.new)]:
            ttk.Button(bar,text=label,command=command).pack(side='right',padx=4)
        split=ttk.Panedwindow(self,orient='horizontal');split.pack(fill='both',expand=True)
        left=ttk.Frame(split,width=230);split.add(left,weight=1)
        self.query=tk.StringVar();ttk.Entry(left,textvariable=self.query).pack(fill='x')
        ttk.Label(left,text='Пошук за назвою / ID').pack(anchor='w',pady=5)
        list_frame=ttk.Frame(left);list_frame.pack(fill='both',expand=True)
        self.list=ttk.Treeview(list_frame,show='tree',selectmode='browse',height=20)
        sb=ttk.Scrollbar(list_frame,command=self.list.yview);sb.pack(side='right',fill='y')
        self.list.configure(yscrollcommand=sb.set);self.list.pack(fill='both',expand=True)
        self.list.bind('<<TreeviewSelect>>',self.select);self.query.trace_add('write',lambda *a:self.filter())
        middle=ttk.Frame(split,width=410);split.add(middle,weight=2)
        canvas=tk.Canvas(middle,highlightthickness=0);scroll=ttk.Scrollbar(middle,command=canvas.yview)
        scroll.pack(side='right',fill='y');canvas.pack(fill='both',expand=True);canvas.configure(yscrollcommand=scroll.set)
        self.form=ttk.Frame(canvas,padding=10);form_id=canvas.create_window(0,0,window=self.form,anchor='nw')
        self.form.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(form_id,width=e.width))
        self.fields={};self.texts={}
        self.ident=tk.StringVar();row(self.form,'Сталий ID',self.ident,readonly=True)
        for key,label in [('name','Назва'),('description','Опис')]+([('trophy','Назва трофея')] if section=='monster' else []):
            self.texts[key]=tk.StringVar();row(self.form,label,self.texts[key])
        self.art=tk.StringVar();self.extra_art={};self.pictures={};self.images={}
        if section=='monster':
            art_row=ttk.Frame(self.form);art_row.pack(fill='x',pady=8)
            for column,(field,label) in enumerate([('sprite_id','Монстр'),('corpse_sprite_id','Труп'),('trophy_sprite_id','Трофей')]):
                art_row.columnconfigure(column,weight=1,uniform='art')
                cell=ttk.Frame(art_row);cell.grid(row=0,column=column,sticky='nsew',padx=2)
                ttk.Label(cell,text=label).pack()
                self.pictures[field]=ttk.Label(cell);self.pictures[field].pack(pady=4)
                if field!='sprite_id':self.extra_art[field]=tk.StringVar()
                ttk.Button(cell,text='Вибрати…',command=lambda f=field:self.choose_art(f),width=11).pack()
            self.picture=self.pictures['sprite_id']
            self.trophy_value=tk.StringVar()
            ttk.Label(cell,text='Базова вартість, кр.',wraplength=110,justify='center').pack(pady=(4,0))
            ttk.Entry(cell,textvariable=self.trophy_value,width=10,justify='center').pack(pady=4)
        else:
            self.picture=ttk.Label(self.form);self.picture.pack(pady=8)
            ttk.Label(self.form,textvariable=self.art,wraplength=340).pack()
            ttk.Button(self.form,text='Вибрати зображення…',command=lambda:self.choose_art('sprite_id')).pack(pady=5)
        for field,label,kind in catalog.FIELDS[section]:
            var=self.trophy_value if field=='trophy_value' else tk.StringVar();self.fields[field]=var
            if field!='trophy_value':row(self.form,label,var,list(kind.values()) if isinstance(kind,dict) else None)
            var.trace_add('write',lambda *args,f=field:self.field_changed(f))
        self.resists={}
        if section=='monster':
            ttk.Label(self.form,text='Опори: від −100% (вразливість) до +100%',wraplength=350).pack(anchor='w',pady=8)
            for kind,label in catalog.DAMAGE.items():
                var=tk.StringVar();self.resists[kind]=var;row(self.form,label+', %',var)
                var.trace_add('write',lambda *args:self.schedule_preview())
            ttk.Label(self.form,text='Поле «armor» старого формату підтримується автоматично.\nФактичний захист у бою визначає «Базовий захист».',wraplength=350).pack(pady=10)
        self.curves=self.penalties=None
        if section=='module':
            self.curves=StatTable(self.form,'Бонуси: 5 значень за рідкістю',self.schedule_preview,True);self.curves.pack(fill='x')
            self.penalties=StatTable(self.form,'Постійні модифікатори (+ / −)',self.schedule_preview);self.penalties.pack(fill='x')
            ttk.Label(self.form,text='Порожня таблиця бонусів: основний параметр × базовий бонус × (рідкість + 1).\nЯкщо таблиця заповнена, вона замінює базовий бонус. Перший рядок посилюється у варіанті з побічним ефектом.',wraplength=350).pack(pady=10)
        right=ttk.Frame(split,padding=(12,0,0,0),width=400);split.add(right,weight=2)
        ttk.Label(right,text='Перегляд за рівнем',font=('Segoe UI',13,'bold')).pack(anchor='w',pady=(0,8))
        self.level=tk.StringVar(value='1');self.tier=tk.StringVar(value=catalog.RARITIES[0]);self.condition=tk.StringVar(value='100')
        self.player_level=tk.StringVar(value='1');self.grade=tk.StringVar(value=catalog.GRADES['normal'])
        self.tradeoff=tk.BooleanVar();self.weak=tk.BooleanVar()
        row(right,'Рівень виду' if section=='monster' else 'Рівень предмета',self.level)
        self.slider=tk.DoubleVar(value=1)
        ttk.Scale(right,from_=1,to=30,variable=self.slider,command=lambda n:self.level.set(str(round(float(n))))).pack(fill='x',pady=4)
        if section=='monster':
            row(right,'Варіант монстра',self.grade,list(catalog.GRADES.values()))
            ttk.Checkbutton(right,text='Ослаблений (рівень виду − 1)',variable=self.weak).pack(anchor='w',pady=4)
        else:
            row(right,'Рідкість',self.tier,catalog.RARITIES)
            if section=='module':ttk.Checkbutton(right,text='Посилений із побічним ефектом',variable=self.tradeoff).pack(anchor='w',pady=4)
            else:row(right,'Стан предмета, 0–100',self.condition)
            if section=='weapon':row(right,'Рівень гравця (постріл)',self.player_level)
        note=('Рівень тут лише для порівняння. У грі вид має заданий базовий рівень, а не рівень зони.' if section=='monster' else
              'Чистий предмет без установлених модулів і перків. Ціна — номінальна; шкода пострілу — без ворога, режиму стрільби та випадкового розкиду.' if section=='weapon' else
              'Таблиця бонусів за рідкістю замінює базовий бонус. Базовий бонус працює лише з порожньою таблицею. Ціна — номінальна.' if section=='module' else
              'Чистий предмет без установлених модулів і перків. Ціна — номінальна, до торгових націнок.')
        ttk.Label(right,text=note,wraplength=365).pack(anchor='w',pady=10)
        self.preview_error=tk.StringVar();ttk.Label(right,textvariable=self.preview_error,foreground='#a0392c',wraplength=365).pack(fill='x')
        table_frame=ttk.Frame(right);table_frame.pack(fill='both',expand=True)
        self.table=ttk.Treeview(table_frame,show='headings',height=15)
        sb=ttk.Scrollbar(table_frame,command=self.table.yview);sb.pack(side='right',fill='y');self.table.configure(yscrollcommand=sb.set);self.table.pack(fill='both',expand=True)
        for var in (self.level,self.tier,self.condition,self.player_level,self.grade,self.tradeoff,self.weak):var.trace_add('write',lambda *args:self.schedule_preview())
        self.status=tk.StringVar();ttk.Label(self,textvariable=self.status).pack(fill='x',pady=(8,0))
        self.rebuild()
        items=self.list.get_children()
        if items:self.open(items[0])

    def rebuild(self):
        self.loading=True;self.list.delete(*self.list.get_children())
        level_key='base_level' if self.section=='monster' else 'min_level' if self.section in ('weapon','armor','helmet') else None
        def sort_key(pair):
            ident,data=pair;name=self.store.data['texts'].get(ident+'.name',ident)
            return (data[level_key] if level_key else 0,name.casefold(),ident)
        for ident,data in sorted(self.store.items(self.section),key=sort_key):
            name=self.store.data['texts'].get(ident+'.name',ident)
            label=(f"Рів. {data[level_key]} · {name}" if level_key else name)
            if self.query.get().casefold() in (label+' '+ident).casefold():self.list.insert('','end',iid=ident,text=label)
        if self.current and self.list.exists(self.current):self.list.selection_set(self.current)
        self.loading=False
        self.status.set(f'{len(self.store.items(self.section))} записів · Зміни застосуються після перезапуску гри')
    def filter(self):
        if self.commit():self.rebuild()
    def select(self,event=None):
        if self.loading or not self.list.selection():return
        ident=self.list.selection()[0]
        if ident==self.current:return
        if self.commit():self.open(ident)
        elif self.current and self.list.exists(self.current):self.list.selection_set(self.current)
    def open(self,ident):
        self.loading=True;self.current=ident;self.original,names=self.store.draft(self.section,ident)
        self.ident.set(ident)
        for key,var in self.texts.items():var.set(names[key])
        self.art.set(self.original['sprite_id'])
        for field,var in self.extra_art.items():var.set(self.original[field])
        for field,_,kind in catalog.FIELDS[self.section]:
            value=self.original.get(field,'pistol' if field=='category' else '')
            self.fields[field].set(kind[value] if isinstance(kind,dict) else str(value))
        for key,var in self.resists.items():var.set(str(self.original.get('resists',{}).get(key,0)))
        if self.curves:self.curves.set(self.original.get('rarity_stats',{}));self.penalties.set(self.original.get('fixed_penalties',{}))
        self.level.set(str(self.original.get('base_level',self.original.get('min_level',1))))
        self.show_art();self.loaded=self.read();self.loading=False;self.refresh_preview()
        if self.list.exists(ident):self.list.selection_set(ident);self.list.see(ident)
    def show_art(self):
        self.image=sprites.photo(self.root,self.art.get(),96);self.picture.configure(image=self.image or '')
        if self.section=='monster':
            self.images['sprite_id']=self.image
            for field,var in self.extra_art.items():
                self.images[field]=sprites.photo(self.root,var.get(),96)
                self.pictures[field].configure(image=self.images[field] or '')
    def choose_art(self,field):
        var=self.art if field=='sprite_id' else self.extra_art[field]
        value=ArtDialog(self.root,var.get()).show()
        if value is not None:var.set(value);self.show_art()
    def read(self):
        data=copy.deepcopy(self.original);names={key:var.get().strip() for key,var in self.texts.items()}
        data['sprite_id']=self.art.get()
        for field,var in self.extra_art.items():data[field]=var.get()
        for field,label,kind in catalog.FIELDS[self.section]:
            text=self.fields[field].get().strip()
            try:value=next(k for k,v in kind.items() if v==text) if isinstance(kind,dict) else kind(text)
            except (ValueError,StopIteration):raise ValueError(label+': некоректне значення')
            data[field]=value
        if self.section=='monster':data['resists']={k:int(v.get()) for k,v in self.resists.items()}
        if self.curves:
            data['rarity_stats']=copy.deepcopy(self.curves.rows);data['fixed_penalties']=copy.deepcopy(self.penalties.rows)
        errors=catalog.validate_definition(self.section,self.current,data,names,self.store.art)
        if errors:raise ValueError('\n'.join(errors))
        return data,names
    def commit(self):
        if not self.current:return True
        try:
            data,names=self.read()
            if (data,names)!=self.loaded:
                self.store.put(self.section,self.current,data,names)
                self.loaded=copy.deepcopy((data,names))
                self.rebuild()
            return True
        except (ValueError,TypeError) as exc:
            messagebox.showerror('Перевірте модель',str(exc),parent=self.root);return False
    def schedule_preview(self):
        if self.loading:return
        if self.pending:self.after_cancel(self.pending)
        self.pending=self.after(150,self.refresh_preview)
    def field_changed(self,field):
        if self.loading:return
        if self.section=='monster' and field=='base_level':
            try:
                level=int(self.fields[field].get())
                if level>=1:self.level.set(str(level))
            except ValueError:pass
        self.schedule_preview()
    def refresh_preview(self):
        self.pending=None
        if not self.current:return
        try:
            data,_=self.read();level=int(self.level.get());condition=float(self.condition.get());player=int(self.player_level.get())
            if not 1<=level<=1000 or not 1<=player<=1000:raise ValueError('Рівень перегляду: 1–1000.')
            if not 0<=condition<=100:raise ValueError('Стан: 0–100.')
            self.slider.set(min(30,level))
            tier=catalog.RARITIES.index(self.tier.get());grade=next(k for k,v in catalog.GRADES.items() if v==self.grade.get())
            levels=list(dict.fromkeys([1,level,level+1,30]))
            values=[catalog.preview(self.section,data,L,tier,condition,player,self.tradeoff.get(),grade,self.weak.get()) for L in levels]
            columns=['stat']+[str(i) for i in range(len(levels))];self.table.configure(columns=columns)
            self.table.heading('stat',text='Параметр');self.table.column('stat',width=140,minwidth=120)
            for i,L in enumerate(levels):self.table.heading(str(i),text=f'Рів. {L}');self.table.column(str(i),width=58,minwidth=45,anchor='e')
            self.table.delete(*self.table.get_children())
            labels=dict(catalog.STATS,weight='Вага, кг',value='Номінал, кр.',slots='Слоти',ap='ОД',shot_damage='Шкода пострілу',hp='Здоров’я',speed='Швидкість',level='Фактичний рівень')
            for key in dict.fromkeys(k for v in values for k in v):
                self.table.insert('','end',values=[labels.get(key,key)]+[f'{v.get(key,0):g}' for v in values])
            self.preview_error.set('Недоступний для появи нижче рівня '+str(data['min_level']) if self.section in ('weapon','armor','helmet') and level<data['min_level'] else '')
        except (ValueError,TypeError,KeyError,OverflowError) as exc:
            self.table.delete(*self.table.get_children());self.preview_error.set(str(exc))
    def new(self):
        if not self.commit():return
        name=simpledialog.askstring('Нова модель','Назва нової моделі (параметри копіюються з обраної):',parent=self.root)
        if name and name.strip():self.create(name)
    def duplicate(self):
        if self.commit() and self.current:self.create(self.texts['name'].get()+' (копія)')
    def create(self,name):
        ident=self.store.add(self.section,name,self.current);self.query.set('');self.rebuild();self.open(ident)
