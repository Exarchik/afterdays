"""Actors, variables, tree editing and a save-independent dialogue play tester."""
import copy,json
import tkinter as tk
from tkinter import ttk,messagebox,simpledialog
from event_editor import Dialog,ArtDialog,row
import sprites
import dialogue_system as ds
from dialogue_text import Presentation, hero, speak_reply


def tag_buttons(parent, target):
    bar=ttk.Frame(parent);bar.pack(anchor='w',pady=3)
    def insert(tag):
        target.insert('insert',tag)
        target.focus_set()
        if isinstance(target,tk.Text):target.see('insert')
    for tag in ('[space]','[time=0.5]','[pause=1.5]','[line]','[clear]'):
        ttk.Button(bar,text=tag,takefocus=False,command=lambda tag=tag:insert(tag)).pack(side='left',padx=2)
    return bar


def fresh(prefix,keys):
    n=1
    while f'{prefix}_{n:03}' in keys:n+=1
    return f'{prefix}_{n:03}'

class ActorDialog(Dialog):
    def __init__(self,parent,actor,hero=False):
        super().__init__(parent,'Актор','600x420');self.name=tk.StringVar(value=actor['name']);self.art=tk.StringVar(value=actor['art'])
        row(self.body,'Ім’я',self.name);self.picture=ttk.Label(self.body);self.picture.pack(pady=12)
        ttk.Button(self.body,text='Вибрати арт…',command=self.choose).pack();self.show_art()
        if hero:ttk.Label(self.body,text='Це запасні ім’я й портрет. У грі використовуються дані створеного гравцем героя.',wraplength=530).pack(pady=15)
    def show_art(self):self.image=sprites.photo(self,self.art.get(),144);self.picture.configure(image=self.image or '')
    def choose(self):
        value=ArtDialog(self,self.art.get()).show()
        if value:self.art.set(value);self.show_art()
    def read(self):
        if not self.name.get().strip():raise ValueError('Вкажіть ім’я актора.')
        return dict(name=self.name.get().strip(),art=self.art.get())

class VariableDialog(Dialog):
    def __init__(self,parent,key=None,value=None):
        super().__init__(parent,'Змінна','600x340');value=value or dict(type='bool',default=False)
        self.key=tk.StringVar(value=key or '');self.kind=tk.StringVar(value=ds.TYPES[value['type']]);self.value=tk.StringVar(value=str(value['default']))
        row(self.body,'ID змінної',self.key,readonly=key is not None);row(self.body,'Тип',self.kind,list(ds.TYPES.values()));row(self.body,'Початкове значення',self.value)
        ttk.Label(self.body,text='Для «Так / ні» введіть так або ні. Змінні спільні для всіх діалогів.',wraplength=530).pack(pady=15)
    def read(self):
        kind=next(k for k,v in ds.TYPES.items() if v==self.kind.get());key=self.key.get().strip()
        import re
        if not re.fullmatch('[a-z][a-z0-9_]*',key):raise ValueError('ID: латинські літери, цифри та підкреслення.')
        return key,dict(type=kind,default=ds.parse_value(self.value.get(),kind))

class RuleDialog(Dialog):
    def __init__(self,parent,doc,quests,rule=None,action=False):
        super().__init__(parent,'Дія відповіді' if action else 'Умова','680x460');self.doc=doc;self.quests=quests;self.action=action
        rule=rule or {};self.kind=tk.StringVar(value={'set':'Задати змінну','add':'Додати до змінної','reward':'Нагорода','quest':'Почати квест','reveal_city':'Відкрити місто','reputation':'Репутація міста'}.get(rule.get('kind'),'Задати змінну'))
        if action:row(self.body,'Дія',self.kind,['Задати змінну','Додати до змінної','Нагорода','Почати квест','Відкрити місто','Репутація міста'])
        self.variable=tk.StringVar(value=rule.get('variable',next(iter(doc['variables']),'')));row(self.body,'Змінна',self.variable,list(doc['variables']))
        self.op=tk.StringVar(value=ds.OPS[rule.get('op','==')])
        if not action:row(self.body,'Порівняння',self.op,list(ds.OPS.values()))
        self.value=tk.StringVar(value=str(rule.get('value','так')));row(self.body,'Значення змінної',self.value)
        self.reward=tk.StringVar(value=ds.REWARDS[rule.get('reward','money')]);self.amount=tk.StringVar(value=str(rule.get('amount',1)))
        self.quest=tk.StringVar(value=rule.get('quest',next(iter(quests),'')))
        if action:
            self.geometry('680x540')
            self.city=tk.StringVar(value=str(rule.get('city',0)));row(self.body,'ID міста (для відкриття / репутації)',self.city)
            row(self.body,'Нагорода',self.reward,list(ds.REWARDS.values()));row(self.body,'Кількість',self.amount)
            row(self.body,'ID квесту',self.quest,list(quests))
            ttk.Label(self.body,text='Заповніть поля обраної дії. Квести беруться з вкладки «Квести». Нагороди та дії відповіді виконуються один раз за сейв.',wraplength=620).pack(pady=12)
    def read(self):
        kind={'Задати змінну':'set','Додати до змінної':'add','Нагорода':'reward','Почати квест':'quest','Відкрити місто':'reveal_city','Репутація міста':'reputation'}[self.kind.get()]
        if self.action and kind in ('reveal_city','reputation'):
            city=int(self.city.get())
            if city<0:raise ValueError('ID міста має бути невід’ємним.')
            result=dict(kind=kind,city=city)
            if kind=='reputation':
                amount=int(self.amount.get())
                if not 1<=amount<=100:raise ValueError('Репутація: від 1 до 100.')
                result['amount']=amount
            return result
        if self.action and kind=='reward':
            amount=int(self.amount.get())
            if not 1<=amount<=1000000:raise ValueError('Кількість: 1–1000000.')
            return dict(kind=kind,reward=next(k for k,v in ds.REWARDS.items() if v==self.reward.get()),amount=amount)
        if self.action and kind=='quest':
            if self.quest.get() not in self.quests:raise ValueError('Спочатку створіть квест у вкладці «Квести».')
            return dict(kind=kind,quest=self.quest.get())
        key=self.variable.get()
        if key not in self.doc['variables']:raise ValueError('Спочатку створіть змінну.')
        value=ds.parse_value(self.value.get(),self.doc['variables'][key]['type'])
        if self.action:
            if kind=='add' and type(value) is not int:raise ValueError('Додавати можна лише до числових змінних.')
            return dict(kind=kind,variable=key,value=value)
        op=next(k for k,v in ds.OPS.items() if v==self.op.get())
        if op not in ('==','!=') and type(value) is not int:raise ValueError('Більше/менше — лише для чисел.')
        return dict(variable=key,op=op,value=value)


def rule_text(r):
    if r.get('kind')=='reveal_city':return f"Відкрити місто {r['city']}"
    if r.get('kind')=='reputation':return f"Місто {r['city']}: +{r['amount']} репутації"
    if 'op' in r:return f"{r['variable']} {ds.OPS[r['op']]} {r['value']}"
    if r['kind'] in ('set','add'):return f"{r['variable']} {'=' if r['kind']=='set' else '+='} {r['value']}"
    if r['kind']=='reward':return f"+{r['amount']} {ds.REWARDS[r['reward']]}"
    return 'Почати квест: '+r['quest']

class Rules(ttk.Frame):
    def __init__(self,parent,doc,quests,rows,action=False):
        super().__init__(parent);self.doc=doc;self.quests=quests;self.rows=copy.deepcopy(rows);self.action=action
        self.list=tk.Listbox(self,height=5,exportselection=False);self.list.pack(fill='both',expand=True)
        bar=ttk.Frame(self);bar.pack(fill='x')
        for label,command in [('+',self.add),('Редагувати',self.edit),('Прибрати',self.remove)]:ttk.Button(bar,text=label,command=command).pack(side='left')
        self.list.bind('<Double-1>',lambda e:self.edit());self.refresh()
    def refresh(self):
        self.list.delete(0,'end')
        for r in self.rows:self.list.insert('end',rule_text(r))
    def add(self):
        value=RuleDialog(self.winfo_toplevel(),self.doc,self.quests,action=self.action).show()
        if value:self.rows.append(value);self.refresh()
    def edit(self):
        selected=self.list.curselection()
        if selected:
            i=selected[0];value=RuleDialog(self.winfo_toplevel(),self.doc,self.quests,self.rows[i],self.action).show()
            if value:self.rows[i]=value;self.refresh()
    def remove(self):
        if self.list.curselection():self.rows.pop(self.list.curselection()[0]);self.refresh()

class ConditionsDialog(Dialog):
    def __init__(self,parent,doc,quests,rows):
        super().__init__(parent,'Умови доступності діалогу','750x410')
        ttk.Label(self.body,text='Усі умови мають виконуватися одночасно. Порожній список — діалог доступний.').pack()
        self.rules=Rules(self.body,doc,quests,rows);self.rules.pack(fill='both',expand=True)
    def read(self):return self.rules.rows

class ReplyDialog(Dialog):
    def __init__(self,parent,doc,quests,reply,nodes=None,new=False):
        super().__init__(parent,'Відповідь гравця','800x680');self.original=copy.deepcopy(reply)
        self.text=tk.StringVar(value=reply['text']);entry=row(self.body,'Текст відповіді',self.text)
        tag_buttons(self.body,entry)
        self.targets={'Завершити діалог':None}
        if new:self.targets['Створити новий блок']='__new__'
        self.targets.update({key+' — '+n['text'][:55]:key for key,n in (nodes or {}).items()})
        target='__new__' if new else reply.get('next')
        self.target=tk.StringVar(value=next((label for label,value in self.targets.items() if value==target),'Завершити діалог'))
        row(self.body,'Після відповіді перейти до',self.target,list(self.targets))
        ttk.Label(self.body,text='Показувати відповідь, якщо виконано всі умови:').pack(anchor='w',pady=8)
        self.conditions=Rules(self.body,doc,quests,reply['conditions']);self.conditions.pack(fill='both',expand=True)
        ttk.Label(self.body,text='Дії після вибору (у зазначеному порядку):').pack(anchor='w',pady=8)
        self.actions=Rules(self.body,doc,quests,reply['actions'],True);self.actions.pack(fill='both',expand=True)
    def read(self):
        if not self.text.get().strip():raise ValueError('Вкажіть текст відповіді.')
        return dict(self.original,text=self.text.get().strip(),conditions=self.conditions.rows,actions=self.actions.rows,next=self.targets[self.target.get()])


class LinkDialog(Dialog):
    def __init__(self,parent,nodes,current):
        super().__init__(parent,'Перехід до спільного блоку','720x260')
        self.targets={'Завершити діалог':None}
        self.targets.update({key+' — '+n['text'][:60]:key for key,n in nodes.items()})
        self.target=tk.StringVar(value=next(label for label,value in self.targets.items() if value==current))
        row(self.body,'Наступний блок',self.target,list(self.targets))
        ttk.Label(self.body,text='Блок може мати кілька вхідних посилань. Циклічні переходи заборонені.',wraplength=650).pack(pady=12)
    def read(self):return {'next':self.targets[self.target.get()]}

class Tester(tk.Toplevel):
    def __init__(self,parent,document,ident,quests):
        super().__init__(parent);self.title('Тест діалогу — окремо від сейву');self.geometry('980x710')
        self.doc=copy.deepcopy(document);self.ident=ident;self.quests=quests
        self.presentation=Presentation(self)
        top=ttk.Frame(self,padding=10);top.pack(fill='x')
        self.name=tk.StringVar(value='Головний герой');ttk.Label(top,text='Ім’я героя').pack(side='left');ttk.Entry(top,textvariable=self.name,width=22).pack(side='left',padx=5)
        ttk.Button(top,text='Скинути тест',command=self.reset).pack(side='right')
        self.dialogue=tk.StringVar(value=ident);ttk.Combobox(top,textvariable=self.dialogue,values=[d['id'] for d in self.doc['dialogues']],state='readonly',width=25).pack(side='left',padx=5)
        ttk.Button(top,text='Відкрити',command=self.switch).pack(side='left')
        area=ttk.Frame(self);area.pack(fill='both',expand=True)
        canvas=tk.Canvas(area,highlightthickness=0);scroll=ttk.Scrollbar(area,command=canvas.yview)
        scroll.pack(side='right',fill='y');canvas.pack(fill='both',expand=True);canvas.configure(yscrollcommand=scroll.set)
        self.content=ttk.Frame(canvas,padding=14);window=canvas.create_window(0,0,window=self.content,anchor='nw')
        self.content.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(window,width=e.width))
        self.status=tk.StringVar();ttk.Label(self,textvariable=self.status,wraplength=920,justify='left',padding=10).pack(fill='x')
        try:self.reset()
        except ValueError as exc:messagebox.showinfo('Діалог недоступний',str(exc),parent=self);self.destroy()
    def reset(self):
        self.session=ds.Session(self.doc,self.ident,self.quests,player_name=self.name.get());self.dialogue.set(self.ident);self.render()
    def switch(self):
        try:self.session.switch(self.dialogue.get());self.render()
        except ValueError as exc:
            self.dialogue.set(self.session.dialogue['id']);messagebox.showinfo('Діалог недоступний',str(exc),parent=self)
    def choose(self,ident=None):
        if self.presentation.player.active:return
        if ident is not None:
            reply=next((r for r in self.session.replies() if r['id']==ident),None)
            if reply:self.render(reply)
            return
        self.finish_choice()
    def finish_choice(self,ident=None):
        try:self.session.choose(ident);self.render()
        except ValueError as exc:messagebox.showerror('Дію не виконано',str(exc),parent=self)
    def render(self,spoken=None):
        self.presentation.cancel()
        for w in self.content.winfo_children():w.destroy()
        s=self.session;n=s.block
        if n:
            actor=hero(s) if spoken else s.actor();self.image=sprites.photo(self,actor['art'],192)
            if self.image:ttk.Label(self.content,image=self.image).pack(side='left',anchor='n',padx=(0,16))
            body=ttk.Frame(self.content);body.pack(fill='both',expand=True)
            ttk.Label(body,text=actor['name'],font=('Segoe UI',17,'bold')).pack(anchor='w',pady=8)
            phrase=ttk.Label(body,text='',wraplength=670,justify='left',font=('Segoe UI',12));phrase.pack(fill='x',pady=15)
            hint=ttk.Label(body);hint.pack(fill='x')
            replies=[];controls=[]
            for r in ([] if spoken else s.replies()):
                button=tk.Button(body,text='',wraplength=620,justify='left',anchor='w',command=lambda i=r['id']:self.choose(i));button.pack(fill='x',pady=5)
                replies.append((button,r['text']));controls.append(button)
            if not spoken and not n['replies']:
                button=ttk.Button(body,text='Далі' if n.get('next') else 'Завершити',command=self.choose);button.pack(fill='x',pady=8);controls.append(button)
            elif not spoken and not s.replies():ttk.Label(body,text='Немає доступних відповідей — перевірте умови гілки.',foreground='#a0392c').pack()
            show_hint=lambda waiting: hint.configure(text='Натисніть будь-яку клавішу або кнопку миші…' if waiting else '')
            if spoken:speak_reply(self.presentation,spoken['text'],phrase,show_hint,lambda:self.finish_choice(spoken['id']))
            else:self.presentation.show(n['text'],phrase,replies,controls,show_hint)
            self.presentation.bind_inputs(self.content)
            if self.presentation.input_tag not in self.bindtags():self.bindtags((self.presentation.input_tag,)+self.bindtags())
            self.focus_set()
        else:ttk.Label(self.content,text='Діалог завершено',font=('Segoe UI',18,'bold')).pack(pady=30)
        self.status.set('Змінні: '+', '.join(f'{k} = {v}' for k,v in s.values.items())+'\nНагороди (тест): '+(', '.join(f'{ds.REWARDS[k]} +{v}' for k,v in s.rewards.items()) or 'немає')+'\nРозпочаті квести (тест): '+(', '.join(s.started) or 'немає'))

class DialoguePanel(ttk.Frame):
    def __init__(self,parent,store,on_save):
        super().__init__(parent,padding=10);self.store=store;self.on_save=on_save;self.current=None;self.current_node=None;self.loading=False
        bar=ttk.Frame(self);bar.pack(fill='x')
        self.selected=tk.StringVar();self.selector=ttk.Combobox(bar,textvariable=self.selected,state='readonly',width=36);self.selector.pack(side='left');self.selector.bind('<<ComboboxSelected>>',self.select_dialogue)
        for label,command in [('+ Діалог',self.add_dialogue),('Актори',self.actors),('Змінні',self.variables),('Протестувати діалог',self.test),('Зберегти всі зміни',on_save)]:ttk.Button(bar,text=label,command=command).pack(side='left',padx=3)
        self.title=tk.StringVar();row(self,'Назва діалогу',self.title)
        ttk.Button(self,text='Умови доступності діалогу…',command=self.conditions).pack(anchor='w',pady=5)
        split=ttk.Panedwindow(self,orient='horizontal');split.pack(fill='both',expand=True)
        left=ttk.Frame(split);split.add(left,weight=1)
        tree_frame=ttk.Frame(left);tree_frame.pack(fill='both',expand=True)
        self.tree=ttk.Treeview(tree_frame,show='tree',selectmode='browse');self.tree.grid(row=0,column=0,sticky='nsew')
        tree_frame.rowconfigure(0,weight=1);tree_frame.columnconfigure(0,weight=1)
        sy=ttk.Scrollbar(tree_frame,command=self.tree.yview);sy.grid(row=0,column=1,sticky='ns')
        sx=ttk.Scrollbar(tree_frame,orient='horizontal',command=self.tree.xview);sx.grid(row=1,column=0,sticky='ew')
        self.tree.configure(yscrollcommand=sy.set,xscrollcommand=sx.set);self.tree.column('#0',width=520,minwidth=250)
        self.tree.bind('<<TreeviewSelect>>',self.select_node)
        bar=ttk.Frame(left);bar.pack(fill='x')
        for label,command in [('+ Відповідь',self.add_reply),('+ Наступна фраза',self.add_next),('Перехід до наявного блоку…',self.link_next),('Видалити блок',self.delete_node)]:ttk.Button(bar,text=label,command=command).pack(fill='x',pady=2)
        right=ttk.Frame(split,padding=10);split.add(right,weight=2)
        self.actor=tk.StringVar();self.actor_box=row(right,'Актор',self.actor,[])
        self.picture=ttk.Label(right);self.picture.pack(pady=5);self.actor_box.bind('<<ComboboxSelected>>',lambda e:self.show_art())
        ttk.Label(right,text='Фраза').pack(anchor='w');self.text=tk.Text(right,height=7,wrap='word');self.text.pack(fill='x');tag_buttons(right,self.text)
        ttk.Label(right,text='Варіанти відповідей гравця (умови й дії — подвійний клік)').pack(anchor='w',pady=8)
        self.replies=tk.Listbox(right,height=8,exportselection=False);self.replies.pack(fill='both',expand=True);self.replies.bind('<Double-1>',lambda e:self.edit_reply())
        ttk.Button(right,text='Редагувати відповідь, умови та дії…',command=self.edit_reply).pack(fill='x',pady=6)
        self.status=tk.StringVar(value='Кілька відповідей можуть вести до одного блоку. Позначка ↪ — посилання на спільну фразу; натисніть, щоб її відкрити.')
        ttk.Label(self,textvariable=self.status,wraplength=1200).pack(fill='x',pady=6)
        self.rebuild()
        if self.doc['dialogues']:self.open(self.doc['dialogues'][0]['id'])
    @property
    def doc(self):return self.store.data['dialogues']
    @property
    def quests(self):return {q['id']:q for q in self.store.data['quests']['quests']}
    @property
    def dialogue(self):return next(d for d in self.doc['dialogues'] if d['id']==self.current)
    def check(self,doc):
        errors=ds.validate(doc,self.store.art,self.quests)
        if errors:raise ValueError('\n'.join(errors))
    def rebuild(self):
        self.selector.configure(values=[d['id']+' — '+d['title'] for d in self.doc['dialogues']])
        self.actor_box.configure(values=[k+' — '+a['name'] for k,a in self.doc['actors'].items()])
        if self.current:
            self.selected.set(self.current+' — '+self.dialogue['title']);self.tree.delete(*self.tree.get_children())
            self.links={};seen=set()
            def add(key,parent=''):
                if key in seen:
                    ref='link:'+str(len(self.links));self.links[ref]=key
                    self.tree.insert(parent,'end',iid=ref,text='↪ '+key+' (спільний блок)');return
                seen.add(key)
                n=self.dialogue['nodes'][key];self.tree.insert(parent,'end',iid=key,text=self.doc['actors'][n['actor']]['name']+': '+n['text'][:55],open=True)
                if n.get('next'):add(n['next'],key)
                for r in n['replies']:
                    label='reply:'+r['id'];self.tree.insert(key,'end',iid=label,text='↳ '+r['text'],open=True)
                    if r.get('next'):add(r['next'],label)
            add(self.dialogue['root'])
    def open(self,ident):
        self.current=ident;self.current_node=None;self.title.set(self.dialogue['title']);self.rebuild();self.open_node(self.dialogue['root'])
    def open_node(self,key):
        self.current_node=key;n=self.dialogue['nodes'][key]
        self.actor.set(n['actor']+' — '+self.doc['actors'][n['actor']]['name'])
        self.text.delete('1.0','end');self.text.insert('1.0',n['text']);self.replies.delete(0,'end')
        for r in n['replies']:self.replies.insert('end',r['text']+f"  [умов: {len(r['conditions'])}; дій: {len(r['actions'])}]")
        self.tree.selection_set(key);self.show_art()
    def show_art(self):
        actor=self.doc['actors'].get(self.actor.get().split(' — ')[0])
        self.image=sprites.photo(self,actor['art'],96) if actor else None;self.picture.configure(image=self.image or '')
    def commit(self):
        if not self.current:return True
        try:
            doc=copy.deepcopy(self.doc);d=next(d for d in doc['dialogues'] if d['id']==self.current);d['title']=self.title.get().strip()
            if self.current_node:d['nodes'][self.current_node].update(actor=self.actor.get().split(' — ')[0],text=self.text.get('1.0','end-1c').strip())
            self.check(doc);self.store.data['dialogues']=doc;return True
        except ValueError as exc:messagebox.showerror('Перевірте діалог',str(exc),parent=self);return False
    def select_dialogue(self,event=None):
        ident=self.selected.get().split(' — ')[0]
        if self.commit():self.open(ident)
    def select_node(self,event=None):
        selected=self.tree.selection()
        if not selected:return
        key=selected[0]
        if key in getattr(self,'links',{}):
            if self.commit():self.open_node(self.links[key])
            return
        if key.startswith('reply:'):
            parent=self.tree.parent(key)
            if parent!=self.current_node:
                if not self.commit():return
                self.open_node(parent)
            replies=self.dialogue['nodes'][parent]['replies'];i=next(i for i,r in enumerate(replies) if r['id']==key[6:]);self.replies.selection_clear(0,'end');self.replies.selection_set(i);return
        if key==self.current_node:return
        if self.commit():self.open_node(key)
        elif self.current_node:self.tree.selection_set(self.current_node)
    def add_dialogue(self):
        if not self.commit():return
        ident=fresh('dialogue',{d['id'] for d in self.doc['dialogues']});actor=next((a for a in self.doc['actors'] if a!='player'),'player')
        self.doc['dialogues'].append(dict(id=ident,title='Новий діалог',root='start',conditions=[],nodes={'start':ds.node(actor)}));self.open(ident)
    def add_reply(self):
        if not self.current_node or not self.commit():return
        n=self.dialogue['nodes'][self.current_node]
        if n['actor']=='player' or n.get('next'):messagebox.showinfo('Відповіді','Відповіді доступні для фраз іншого актора без прямого переходу.',parent=self);return
        rid=fresh('answer',{r['id'] for n in self.dialogue['nodes'].values() for r in n['replies']})
        reply=dict(id=rid,text='Нова відповідь',conditions=[],actions=[],next=None)
        value=ReplyDialog(self,self.doc,self.quests,reply,self.dialogue['nodes'],new=True).show()
        if value:
            doc=copy.deepcopy(self.doc);d=next(d for d in doc['dialogues'] if d['id']==self.current)
            if value['next']=='__new__':
                key=fresh('block',d['nodes']);d['nodes'][key]=ds.node(n['actor']);value['next']=key
            d['nodes'][self.current_node]['replies'].append(value)
            self.apply_graph(doc,value.get('next') or self.current_node)
    def add_next(self):
        if not self.current_node or not self.commit():return
        n=self.dialogue['nodes'][self.current_node]
        if n['replies'] or n.get('next'):messagebox.showinfo('Перехід уже є','Оберіть кінцевий блок гілки.',parent=self);return
        key=fresh('block',self.dialogue['nodes']);self.dialogue['nodes'][key]=ds.node(n['actor']);n['next']=key;self.rebuild();self.open_node(key)
    def edit_reply(self):
        selected=self.replies.curselection()
        if not selected or not self.commit():return
        n=self.dialogue['nodes'][self.current_node];i=selected[0]
        value=ReplyDialog(self,self.doc,self.quests,n['replies'][i],self.dialogue['nodes']).show()
        if value:
            doc=copy.deepcopy(self.doc);d=next(d for d in doc['dialogues'] if d['id']==self.current)
            d['nodes'][self.current_node]['replies'][i]=value
            self.apply_graph(doc,self.current_node)
    def apply_graph(self,doc,selected):
        d=next(d for d in doc['dialogues'] if d['id']==self.current);ds.prune_unreachable(d)
        try:self.check(doc)
        except ValueError as exc:messagebox.showerror('Перехід не застосовано',str(exc),parent=self);return False
        self.store.data['dialogues']=doc;self.rebuild();self.open_node(selected if selected in d['nodes'] else d['root']);return True
    def link_next(self):
        if not self.current_node or not self.commit():return
        n=self.dialogue['nodes'][self.current_node]
        if n['replies']:messagebox.showinfo('Перехід відповіді','Оберіть продовження в редакторі відповідної відповіді.',parent=self);return
        value=LinkDialog(self,self.dialogue['nodes'],n.get('next')).show()
        if value is None:return
        doc=copy.deepcopy(self.doc);d=next(d for d in doc['dialogues'] if d['id']==self.current)
        d['nodes'][self.current_node]['next']=value['next'];self.apply_graph(doc,self.current_node)
    def delete_node(self):
        if not self.current_node or not self.commit():return
        if self.current_node==self.dialogue['root']:messagebox.showinfo('Початковий блок','Початковий блок не можна видалити.',parent=self);return
        if not messagebox.askyesno('Видалити блок','Видалити блок і всі посилання на нього? Продовження, доступні через інші гілки, залишаться.',parent=self):return
        doc=copy.deepcopy(self.doc);d=next(d for d in doc['dialogues'] if d['id']==self.current)
        nodes=d['nodes'];key=self.current_node;del nodes[key]
        for n in nodes.values():
            if n.get('next')==key:n['next']=None
            n['replies'][:]=[r for r in n['replies'] if r.get('next')!=key]
        self.apply_graph(doc,d['root'])
    def conditions(self):
        if not self.current or not self.commit():return
        value=ConditionsDialog(self,self.doc,self.quests,self.dialogue['conditions']).show()
        if value is not None:self.dialogue['conditions']=value
    def actors(self):self.manage(False)
    def variables(self):self.manage(True)
    def manage(self,variables):
        if not self.commit():return
        win=tk.Toplevel(self);win.title('Змінні діалогів' if variables else 'Актори діалогів');win.geometry('620x420');win.transient(self.winfo_toplevel())
        listing=tk.Listbox(win,exportselection=False);listing.pack(fill='both',expand=True,padx=12,pady=12)
        group='variables' if variables else 'actors'
        def refresh():
            listing.delete(0,'end')
            for key,value in self.doc[group].items():listing.insert('end',key+' — '+(str(value['default'])+' ('+ds.TYPES[value['type']]+')' if variables else value['name']))
        def edit(add=False):
            selected=listing.curselection();key=None if add else list(self.doc[group])[selected[0]] if selected else None
            if not add and key is None:return
            if variables:
                value=VariableDialog(win,key,self.doc[group].get(key)).show()
                if value is None:return
                ident,data=value
                if add and ident in self.doc[group]:messagebox.showerror('Змінна вже є',ident,parent=win);return
            else:
                ident=key or fresh('actor',self.doc[group]);data=ActorDialog(win,self.doc[group].get(key,dict(name='Новий актор',art='npc:traveler')),key=='player').show()
                if data is None:return
            doc=copy.deepcopy(self.doc);doc[group][ident]=data
            try:self.check(doc)
            except ValueError as exc:messagebox.showerror('Зміну не застосовано',str(exc),parent=win);return
            self.store.data['dialogues']=doc;refresh();self.rebuild()
            if self.current_node:self.open_node(self.current_node)
        bar=ttk.Frame(win);bar.pack(fill='x',padx=12,pady=10)
        ttk.Button(bar,text='+',command=lambda:edit(True)).pack(side='left');ttk.Button(bar,text='Редагувати',command=edit).pack(side='left');listing.bind('<Double-1>',lambda e:edit());refresh()
    def test(self):
        if self.current and self.commit():return Tester(self,self.doc,self.current,self.quests)
