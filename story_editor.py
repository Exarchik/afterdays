"""Form-based assembly of ordered quest and dialogue modules."""
import copy
import tkinter as tk
from tkinter import ttk,messagebox,simpledialog
import story_system

KINDS={'dialogue':'Діалог','quest':'Авторський квест','visit':'Прибуття до міста'}


class StoryEditor(tk.Toplevel):
    def __init__(self,parent,store):
        super().__init__(parent);self.store=store;self.current=None;self.stages=[]
        self.title('Модульні сюжетні лінії');self.geometry('880x650');self.transient(parent.winfo_toplevel());self.grab_set()
        bar=ttk.Frame(self,padding=10);bar.pack(fill='x')
        self.selected=tk.StringVar();self.selector=ttk.Combobox(bar,textvariable=self.selected,state='readonly',width=45);self.selector.pack(side='left')
        self.selector.bind('<<ComboboxSelected>>',self.select)
        ttk.Button(bar,text='Нова лінія',command=self.add).pack(side='left',padx=8)
        body=ttk.Frame(self,padding=12);body.pack(fill='both',expand=True)
        self.title_var=tk.StringVar();self.enabled=tk.BooleanVar(value=True)
        ttk.Label(body,text='Назва сюжетної лінії').pack(anchor='w');ttk.Entry(body,textvariable=self.title_var).pack(fill='x')
        ttk.Checkbutton(body,text='Доступна для початку в грі',variable=self.enabled).pack(anchor='w',pady=6)
        self.moves=tk.StringVar(value='0')
        ttk.Label(body,text='Автостарт після кроків у новій грі (0 — ручний початок)').pack(anchor='w')
        ttk.Entry(body,textvariable=self.moves,width=10).pack(anchor='w')
        ttk.Label(body,text='Етапи виконуються згори вниз. Квест завершується після здачі; діалог — після останньої репліки.\nКвести створюйте у вкладці «Квести», розмови — у вкладці «Діалоги».',wraplength=820).pack(anchor='w',pady=8)
        self.list=tk.Listbox(body,exportselection=False);self.list.pack(fill='both',expand=True)
        row=ttk.Frame(body);row.pack(fill='x',pady=10)
        self.kind=tk.StringVar(value='Діалог');kind=ttk.Combobox(row,textvariable=self.kind,values=list(KINDS.values()),state='readonly',width=23);kind.pack(side='left');kind.bind('<<ComboboxSelected>>',lambda e:self.references())
        self.ref=tk.StringVar();self.refs=ttk.Combobox(row,textvariable=self.ref,width=42);self.refs.pack(side='left',padx=6)
        ttk.Button(row,text='Додати етап',command=self.add_stage).pack(side='left')
        controls=ttk.Frame(body);controls.pack(fill='x')
        for label,command in [('↑',lambda:self.move(-1)),('↓',lambda:self.move(1)),('Видалити етап',self.remove),('Застосувати',self.apply)]:ttk.Button(controls,text=label,command=command).pack(side='left',padx=3)
        self.status=tk.StringVar(value='Після застосування натисніть «Зберегти всі зміни» у головному редакторі.')
        ttk.Label(body,textvariable=self.status,wraplength=820).pack(fill='x',pady=10)
        self.protocol('WM_DELETE_WINDOW',self.close);self.refresh();self.references()
        stories=self.store.data['quests'].get('stories',[])
        if stories:self.open(stories[0]['id'])

    def refresh(self):self.selector['values']=[s['id']+' — '+s['title'] for s in self.store.data['quests'].get('stories',[])]
    def references(self):
        kind=next(k for k,v in KINDS.items() if v==self.kind.get())
        values=[d['id']+' — '+d['title'] for d in self.store.data['dialogues']['dialogues']] if kind=='dialogue' else [q['id']+' — '+q['title'] for q in self.store.data['quests']['quests']] if kind=='quest' else []
        self.refs.configure(values=values,state='normal' if kind=='visit' else 'readonly');self.ref.set(values[0] if values else '0' if kind=='visit' else '')
    def open(self,ident):
        s=next(s for s in self.store.data['quests']['stories'] if s['id']==ident)
        self.current=ident;self.selected.set(ident+' — '+s['title']);self.title_var.set(s['title']);self.enabled.set(s['enabled']);self.stages=copy.deepcopy(s['stages']);self.rebuild()
        self.moves.set(str(s.get('start_after_moves',0)))
    def select(self,event=None):
        ident=self.selected.get().split(' — ')[0]
        if self.apply():self.open(ident)
        elif self.current:self.selected.set(self.current)
    def rebuild(self):
        self.list.delete(0,'end')
        for i,s in enumerate(self.stages):self.list.insert('end',f"{i+1}. {KINDS[s['kind']]}: {s['ref']}")
    def add(self):
        if not self.apply():return
        ident=simpledialog.askstring('Нова сюжетна лінія','Сталий ID (латиниця, цифри, підкреслення):',parent=self)
        if not ident:return
        import re
        if not re.fullmatch('[a-z][a-z0-9_]*',ident) or any(s['id']==ident for s in self.store.data['quests'].get('stories',[])):
            messagebox.showerror('Некоректний ID','Вкажіть унікальний ID, починаючи з літери.',parent=self);return
        self.current=ident;self.selected.set(ident);self.title_var.set('Головна сюжетна лінія');self.enabled.set(True);self.stages=[];self.rebuild()
        self.moves.set('0')
    def add_stage(self):
        if not self.current:return
        kind=next(k for k,v in KINDS.items() if v==self.kind.get());ref=self.ref.get().split(' — ')[0]
        try:
            if kind=='visit':ref=int(ref)
            if ref=='':raise ValueError()
        except ValueError:messagebox.showerror('Етап','Оберіть квест/діалог або введіть числовий ID міста.',parent=self);return
        self.stages.append(dict(kind=kind,ref=ref));self.rebuild()
    def move(self,delta):
        selected=self.list.curselection()
        if not selected:return
        i=selected[0];j=i+delta
        if 0<=j<len(self.stages):self.stages[i],self.stages[j]=self.stages[j],self.stages[i];self.rebuild();self.list.selection_set(j)
    def remove(self):
        selected=self.list.curselection()
        if selected:self.stages.pop(selected[0]);self.rebuild()
    def apply(self):
        if not self.current:return True
        doc=copy.deepcopy(self.store.data['quests']);stories=doc.setdefault('stories',[])
        value=dict(id=self.current,title=self.title_var.get().strip(),enabled=self.enabled.get(),stages=copy.deepcopy(self.stages))
        try:
            moves=int(self.moves.get())
            if moves<0:raise ValueError()
        except ValueError:
            messagebox.showerror('Автостарт','Введіть невід’ємну цілу кількість кроків.',parent=self);return False
        if moves:value['start_after_moves']=moves
        stories[:]=[s for s in stories if s['id']!=self.current]+[value]
        errors=story_system.validate(doc,self.store.data['dialogues'])
        if errors:messagebox.showerror('Перевірте сюжет','\n'.join(errors),parent=self);return False
        self.store.data['quests']=doc;self.refresh();self.status.set('Застосовано. Збережіть усі зміни у головному редакторі.');return True
    def close(self):
        if self.apply() or messagebox.askyesno('Закрити','Відкинути незастосовані зміни сюжетної лінії?',parent=self):self.destroy()
