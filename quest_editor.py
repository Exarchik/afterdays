"""Form-based quest catalog editing with a browsable guide to native quest types."""
import copy
import tkinter as tk
from tkinter import ttk,messagebox
import quest_catalog as catalog

FIELDS=[('title','Назва',str),('min_level','Рівень героя: від',int),('max_level','Рівень героя: до',int),
('min_reputation','Репутація в місті: від',int),('max_reputation','Репутація в місті: до',int),
('min_turn','Не раніше ходу',int),('cities','ID міст через кому (порожньо = усі)',list),
('requires','Попередні квести: ID через кому',list),('cooldown','Повтор через ходів після здачі/скасування',int),
('goal','Кількість для полювання / трофеїв',int),('food_need','Їжа для постачання',int),('med_need','Аптечки для постачання',int),
('reward','Базові кредити (рівень 1)',int),('xp_reward','Базовий XP (рівень 1)',int),
('art','ID арту',str),('money_power','Степінь рівня для кредитів (0 = фіксовано)',float),('xp_step','XP за наступний рівень',int)]

class QuestPanel(ttk.Frame):
    def __init__(self,parent,store,on_save):
        super().__init__(parent);self.store=store;self.on_save=on_save;self.current=None;self.loading=False
        self.status=tk.StringVar(value='Оберіть вбудований тип або авторський квест. Звичайні й елітні варіанти мають окремі нагороди та умови.')
        bar=ttk.Frame(self);bar.pack(fill='x',padx=8,pady=6)
        ttk.Button(bar,text='Сюжетні лінії',command=self.stories).pack(side='left',padx=3)
        for label,command in [('Новий квест',self.add),('Дублювати',self.duplicate),('Видалити',self.delete),('Зберегти всі зміни',on_save)]:
            ttk.Button(bar,text=label,command=command).pack(side='left',padx=3)
        split=ttk.Panedwindow(self,orient='horizontal');split.pack(fill='both',expand=True)
        left=ttk.Frame(split);split.add(left,weight=1)
        self.search=tk.StringVar();ttk.Entry(left,textvariable=self.search).pack(fill='x',padx=5,pady=5)
        self.search.trace_add('write',lambda *_:self.rebuild())
        self.tree=ttk.Treeview(left,show='tree',selectmode='browse');self.tree.pack(side='left',fill='both',expand=True)
        scroll=ttk.Scrollbar(left,command=self.tree.yview);scroll.pack(side='right',fill='y');self.tree.configure(yscrollcommand=scroll.set)
        self.tree.bind('<<TreeviewSelect>>',self.select)
        right=ttk.Frame(split);split.add(right,weight=3)
        canvas=tk.Canvas(right,highlightthickness=0);scroll=ttk.Scrollbar(right,command=canvas.yview)
        scroll.pack(side='right',fill='y');canvas.pack(side='left',fill='both',expand=True);canvas.configure(yscrollcommand=scroll.set)
        self.form=ttk.Frame(canvas,padding=12);window=canvas.create_window(0,0,window=self.form,anchor='nw')
        self.form.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(window,width=e.width))
        self.heading=ttk.Label(self.form,text='Квести',font=('Segoe UI',14,'bold'));self.heading.pack(anchor='w')
        self.help=ttk.Label(self.form,wraplength=690,justify='left');self.help.pack(fill='x',pady=8)
        self.editor=ttk.Frame(self.form);self.editor.pack(fill='both',expand=True)
        self.vars={};self.inputs={}
        for row,(key,label,kind) in enumerate([('id','ID (сталий)',str),('kind','Тип квесту',str)]+FIELDS):
            ttk.Label(self.editor,text=label).grid(row=row,column=0,sticky='w',padx=4,pady=4)
            var=tk.StringVar();self.vars[key]=var
            entry=ttk.Combobox(self.editor,textvariable=var,values=[k+' — '+v[0] for k,v in catalog.TYPES.items()],state='readonly') if key=='kind' else ttk.Entry(self.editor,textvariable=var,state='readonly' if key=='id' else 'normal')
            entry.grid(row=row,column=1,sticky='ew',padx=4,pady=4);self.inputs[key]=entry
        self.editor.columnconfigure(1,weight=1)
        row=len(FIELDS)+2
        for key,label in [('enabled','Увімкнено'),('repeatable','Повторюваний (інакше одноразовий)'),('elite','Елітний квест (нагороди задаються вище без прихованого множника)')]:
            self.vars[key]=tk.BooleanVar();ttk.Checkbutton(self.editor,text=label,variable=self.vars[key]).grid(row=row,column=0,columnspan=2,sticky='w',pady=5);row+=1
        ttk.Label(self.editor,text='Опис квесту').grid(row=row,column=0,sticky='w');row+=1
        self.description=tk.Text(self.editor,height=6,wrap='word');self.description.grid(row=row,column=0,columnspan=2,sticky='ew')
        ttk.Label(self,textvariable=self.status,wraplength=1200).pack(fill='x',padx=8,pady=5)
        from quest_profile_editor import NativeQuestForm
        self.native=NativeQuestForm(self.form,store)
        self.author_preview=ttk.Label(self.editor,wraplength=650,justify='left')
        self.author_preview.grid(row=row+1,column=0,columnspan=2,sticky='w',pady=8)
        ttk.Button(self.editor,text='Вибрати арт…',command=self.pick_art).grid(row=row+2,column=0,sticky='w')
        self.author_art=tk.Canvas(self.editor,width=96,height=96,highlightthickness=0)
        self.author_art.grid(row=row+2,column=1,sticky='w')
        self.vars['art'].trace_add('write',lambda *_:self.preview_art())
        for key in ('reward','xp_reward','money_power','xp_step'):
            self.vars[key].trace_add('write',lambda *_:self.preview_rewards())
        self.rebuild();self.editor.pack_forget()

    @property
    def document(self):return self.store.data['quests']

    def stories(self):
        owner=self.master.master
        commit=owner.commit if hasattr(owner,'commit') else self.commit
        if commit():
            from story_editor import StoryEditor
            StoryEditor(self,self.store)

    def rebuild(self):
        self.loading=True
        try:
            self.tree.delete(*self.tree.get_children())
            query=self.search.get().casefold()
            for group,title,items in [('types','Вбудовані квести: звичайні / елітні',catalog.TYPES),('special','Сюжетні / автоматичні типи',catalog.SPECIAL)]:
                self.tree.insert('', 'end',iid=group,text=title,open=True)
                for key,(name,help_text) in items.items():
                    if query in (key+' '+name).casefold():self.tree.insert(group,'end',iid='type:'+key,text=name)
            self.tree.insert('','end',iid='quests',text='Окремі авторські квести',open=True)
            for q in self.document['quests']:
                if query in (q['title']+' '+q['id']).casefold():self.tree.insert('quests','end',iid='quest:'+q['id'],text=('✓ ' if q['enabled'] else '○ ')+q['title'])
        finally:self.loading=False

    def select(self,event=None):
        if self.loading:return
        selected=self.tree.selection()
        if not selected:return
        key=selected[0]
        if key=='quest:'+str(self.current):return
        if not self.commit():
            if self.current and self.tree.exists('quest:'+self.current):self.tree.selection_set('quest:'+self.current)
            return
        self.current=None;self.editor.pack_forget();self.native.pack_forget();self.native.kind=None
        if key.startswith('quest:'):self.open(key[6:])
        elif key.startswith('type:'):
            ident=key[5:];name,help_text={**catalog.TYPES,**catalog.SPECIAL}[ident]
            self.heading.config(text=name)
            self.native.open(ident);self.native.pack(fill='both',expand=True)
            self.help.config(text=help_text+'\n'+('Налаштування всіх нових квестів цього типу.' if ident in catalog.TYPES else 'Створюється сюжетною механікою гри; не є окремим контрактом мера.'))
        else:self.heading.config(text='Квести');self.help.config(text='Оберіть тип для редагування або створіть окремий квест.')

    def open(self,ident):
        self.native.pack_forget();self.native.kind=None
        q=next(q for q in self.document['quests'] if q['id']==ident);self.current=ident
        self.heading.config(text=q['title']);self.help.config(text='Усі умови діють одночасно. Міста мають ID від 0. Попередники — завершені авторські квести. Для появи також потрібні одержувач, придатна місцевість та інші передумови відповідного типу. Змінені нагороди не впливають на вже прийняті квести.')
        self.editor.pack(fill='both',expand=True)
        for key,var in self.vars.items():
            value=q.get(key,{'art':'','money_power':0,'xp_step':0,'elite':False}.get(key,''))
            if key=='kind':value=value+' — '+catalog.TYPES[value][0]
            elif isinstance(value,list):value=', '.join(map(str,value))
            var.set(value)
        self.description.delete('1.0','end');self.description.insert('1.0',q['description'])

    def commit(self):
        if not self.native.commit():return False
        if not self.current:return True
        try:
            q=copy.deepcopy(next(q for q in self.document['quests'] if q['id']==self.current))
            for key,label,kind in FIELDS:
                text=self.vars[key].get().strip()
                if kind in (int,float):q[key]=kind(text)
                elif kind is list:q[key]=[int(v.strip()) if key=='cities' else v.strip() for v in text.split(',') if v.strip()]
                else:q[key]=text
            q['kind']=self.vars['kind'].get().split(' — ')[0]
            for key in ('enabled','repeatable','elite'):q[key]=self.vars[key].get()
            q['description']=self.description.get('1.0','end-1c')
            doc=copy.deepcopy(self.document);index=next(i for i,v in enumerate(doc['quests']) if v['id']==self.current);doc['quests'][index]=q
            errors=catalog.validate(doc)
            if errors:raise ValueError('\n'.join(errors))
            self.store.data['quests']=doc
            if self.tree.exists('quest:'+self.current):self.tree.item('quest:'+self.current,text=('✓ ' if q['enabled'] else '○ ')+q['title'])
            return True
        except (ValueError,StopIteration) as exc:
            messagebox.showerror('Некоректний квест',str(exc),parent=self);return False

    def pick_art(self):
        from event_editor import ArtDialog
        value=ArtDialog(self.winfo_toplevel(),self.vars['art'].get()).show()
        if value:self.vars['art'].set(value)

    def preview_art(self):
        import sprites
        self.author_art.delete('all')
        self.author_photo=sprites.photo(self.author_art,self.vars['art'].get(),96)
        if self.author_photo:self.author_art.create_image(48,48,image=self.author_photo)

    def preview_rewards(self):
        try:
            from quest_profiles import rewards
            spec={key:float(self.vars[key].get()) for key in ('reward','xp_reward','money_power','xp_step')}
            if not 0<=spec['money_power']<=3:raise ValueError()
            self.author_preview.config(text='Кредити = база × рівень^степінь; XP = база + приріст × (рівень − 1).\n'+
                '  |  '.join(f'L{level}: {rewards(spec,level)[0]} кр. / {rewards(spec,level)[1]} XP' for level in (1,2,5,10)))
        except (ValueError,OverflowError):self.author_preview.config(text='Введіть коректні значення нагород.')

    def new_id(self):
        ids={q['id'] for q in self.document['quests']};n=1
        while f'quest_custom_{n:03}' in ids:n+=1
        return f'quest_custom_{n:03}'

    def add(self):
        if not self.commit():return
        q=catalog.draft(self.new_id());selected=self.tree.selection()
        if selected and selected[0].startswith('type:') and selected[0][5:] in catalog.TYPES:q['kind']=selected[0][5:]
        self.document['quests'].append(q);self.rebuild();self.open(q['id']);self.tree.selection_set('quest:'+q['id'])
        self.status.set('Новий квест · Збережіть усі зміни, потім перезапустіть гру.')

    def duplicate(self):
        if not self.current or not self.commit():return
        q=copy.deepcopy(next(q for q in self.document['quests'] if q['id']==self.current));q.update(id=self.new_id(),title=q['title']+' (копія)')
        self.document['quests'].append(q);self.rebuild();self.open(q['id']);self.tree.selection_set('quest:'+q['id'])

    def delete(self):
        if not self.current:return
        if any(s['kind']=='quest' and s['ref']==self.current for story in self.document.get('stories',[]) for s in story['stages']):
            messagebox.showerror('Квест використовується','Спочатку приберіть його з етапів сюжетної лінії.',parent=self);return
        if any(self.current in q['requires'] for q in self.document['quests']):
            messagebox.showerror('Квест використовується','Спочатку приберіть його з умов появи інших квестів.',parent=self);return
        if not messagebox.askyesno('Видалити квест','Видалити визначення квесту? Уже прийняті квести залишаться в сейвах.',parent=self):return
        self.document['quests'][:]=[q for q in self.document['quests'] if q['id']!=self.current]
        self.current=None;self.editor.pack_forget();self.rebuild()
