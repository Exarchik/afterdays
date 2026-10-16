"""Special location templates and coarse/fine merchant stock editing."""
import copy
import tkinter as tk
from tkinter import ttk,messagebox,simpledialog
import special_sites as rules
import sprites
from event_editor import Dialog,ArtDialog,row
from faction_editor import CatalogPanel


class StockDialog(Dialog):
    def __init__(self,parent,store,value=None):
        super().__init__(parent,'Товар торговця','730x580')
        self.store=store;self.value=value or {};self.kinds={v:k for k,v in rules.KINDS.items()}
        self.kind=tk.StringVar(value=rules.KINDS[self.value.get('kind','food')])
        row(self.body,'Категорія',self.kind,list(self.kinds)).bind('<<ComboboxSelected>>',self.choices)
        self.item=tk.StringVar();self.item_field=row(self.body,'Предмет',self.item,[])
        self.amount=tk.StringVar(value=str(self.value.get('amount',1)));row(self.body,'Кількість',self.amount)
        self.chance=tk.StringVar(value=str(self.value.get('chance',1)*100));row(self.body,'Шанс появи, %',self.chance)
        self.low=tk.StringVar(value=str(self.value.get('rarity_min',0)))
        self.high=tk.StringVar(value=str(self.value.get('rarity_max',4)))
        self.low_field=row(self.body,'Рідкість від (0–4)',self.low,list(range(5)))
        self.high_field=row(self.body,'Рідкість до (0–4)',self.high,list(range(5)))
        ttk.Label(self.body,text='«Випадковий із категорії» — загальне правило. Конкретний предмет — точне налаштування.\nДля їжі, ліків, набоїв і матеріалів кількість означає розмір стопки;\nдля спорядження й модулів — число окремих предметів.\nПредмети стають доступними з їхнього мінімального рівня.\nСтандартні обмеження рідкісності й репутації у грі зберігаються.',wraplength=660).pack(pady=16)
        self.choices(initial=True)

    def choices(self,event=None,initial=False):
        kind=self.kinds[self.kind.get()];self.options={'Випадковий із категорії':''}
        group='modules' if kind=='module' else 'equipment' if kind in ('equipment','weapon','armor','helmet') else 'consumables'
        for key,d in self.store.data[group].items():
            if kind not in ('equipment','module') and d['kind']!=kind:continue
            name=d.get('name') or self.store.data['texts'].get(key+'.name',key)
            self.options[f'{name} [{key}]']=key
        desired=self.value.get('item_id','') if initial else ''
        self.item.set(next((label for label,key in self.options.items() if key==desired),'Випадковий із категорії'))
        self.item_field.configure(values=list(self.options))
        for field in (self.low_field,self.high_field):field.configure(state='readonly' if group in ('equipment','modules') else 'disabled')

    def read(self):
        value=dict(kind=self.kinds[self.kind.get()],amount=int(self.amount.get()),chance=float(self.chance.get())/100,
                   rarity_min=int(self.low.get()),rarity_max=int(self.high.get()))
        if self.options[self.item.get()]:value['item_id']=self.options[self.item.get()]
        sample=dict(name='Тест',npc='Тест',npc_art=next(iter(self.store.art)),role='merchant',refresh_turns=100,stock=[value])
        errors=rules.validate({'test':sample},self.store.art,self.store.data['equipment'],self.store.data['modules'],self.store.data['consumables'])
        if errors:raise ValueError('\n'.join(errors))
        return value


class SitePanel(CatalogPanel):
    def __init__(self,parent,store,save):
        super().__init__(parent,store,'special_sites',save)
        # The base list is shared with other editor sections; add its scrollbar here.
        bar=ttk.Scrollbar(self.list.master,command=self.list.yview);bar.pack(side='right',fill='y',before=self.list)
        self.list.configure(yscrollcommand=bar.set)
        self.npc=tk.StringVar();row(self.form,'Ім’я мешканця',self.npc)
        self.role=tk.StringVar();row(self.form,'Тип персонажа',self.role,list(rules.ROLES.values()))
        portraits=ttk.Frame(self.form);portraits.pack(fill='x',pady=6)
        npc_frame=ttk.Frame(portraits);npc_frame.pack(side='left',fill='x',expand=True)
        site_frame=ttk.Frame(portraits);site_frame.pack(side='left',fill='x',expand=True)
        self.art=tk.StringVar();row(npc_frame,'Арт персонажа',self.art,readonly=True)
        self.preview=tk.Canvas(npc_frame,width=96,height=96,highlightthickness=0,bg='#24372c');self.preview.pack()
        ttk.Button(npc_frame,text='Вибрати арт персонажа',command=self.choose_art).pack()
        self.location_art=tk.StringVar();row(site_frame,'Арт локації',self.location_art,readonly=True)
        self.location_preview=tk.Canvas(site_frame,width=96,height=96,highlightthickness=0,bg='#24372c');self.location_preview.pack()
        ttk.Button(site_frame,text='Вибрати арт локації',command=self.choose_location_art).pack()
        ttk.Button(site_frame,text='Прибрати арт локації',command=self.clear_location_art).pack()
        self.refresh_turns=tk.StringVar();row(self.form,'Оновлення товарів, ходів',self.refresh_turns)
        ttk.Label(self.form,text='Асортимент (для персонажів, які торгують)',font=('Segoe UI',11,'bold')).pack(pady=(12,4))
        self.stock=[];self.stock_list=tk.Listbox(self.form,height=8,exportselection=False)
        self.stock_list.pack(fill='x');self.stock_list.bind('<Double-Button-1>',lambda e:self.edit_stock())
        buttons=ttk.Frame(self.form);buttons.pack(fill='x')
        for text,command in [('+ Товар',self.add_stock),('Редагувати',self.edit_stock),('Прибрати товар',self.remove_stock)]:ttk.Button(buttons,text=text,command=command).pack(side='left')
        presets=ttk.Frame(self.form);presets.pack(fill='x',pady=5)
        for label,kinds in [('Їжа й ліки',('food','med','rad')),('Спорядження',('weapon','armor','helmet','module')),('Матеріали',('parts','fragments','repairkit','ammo'))]:
            ttk.Button(presets,text='+ '+label,command=lambda kinds=kinds:self.preset(kinds)).pack(side='left')
        ttk.Button(self.form,text='Видалити локацію',command=self.delete).pack(anchor='w',pady=10)
        ttk.Label(self.form,text='Географія доданих і видалених локацій оновлюється в новій грі.\nНазви, мешканці та асортимент наявних локацій — після перезапуску й завантаження.\nДля квестодавця використовуються стандартні квести особливої локації.',wraplength=700).pack(anchor='w')
        self.rebuild()
        if self.entries:self.open(next(iter(self.entries)))

    @property
    def entries(self):return self.store.data['special_sites']

    def open(self,ident):
        self.current=ident;d=self.entries[ident]
        self.ident.set(ident);self.name.set(d['name']);self.npc.set(d['npc']);self.role.set(rules.ROLES[d['role']])
        self.art.set(d['npc_art']);self.location_art.set(d.get('location_art',''));self.refresh_turns.set(str(d['refresh_turns']));self.stock=copy.deepcopy(d['stock'])
        self.refresh_stock();self.show_art()

    def show_art(self):
        self.preview.delete('all');sprites.draw(self.preview,self.art.get(),0,0,96)
        self.location_preview.delete('all');sprites.draw(self.location_preview,self.location_art.get(),0,0,96)

    def choose_art(self):
        result=ArtDialog(self.root,self.art.get()).show()
        if result:self.art.set(result);self.show_art()

    def choose_location_art(self):
        result=ArtDialog(self.root,self.location_art.get()).show()
        if result:self.location_art.set(result);self.show_art()

    def clear_location_art(self):
        self.location_art.set('');self.show_art()

    def refresh_stock(self):
        self.stock_list.delete(0,'end')
        for d in self.stock:
            self.stock_list.insert('end',f"{rules.KINDS[d['kind']]} · {d.get('item_id','випадковий')} ×{d['amount']} · {d.get('chance',1)*100:g}% · рідкість {d.get('rarity_min',0)}–{d.get('rarity_max',4)}")

    def add_stock(self):
        value=StockDialog(self.root,self.store).show()
        if value:self.stock.append(value);self.refresh_stock()

    def edit_stock(self):
        selected=self.stock_list.curselection()
        if not selected:return
        index=selected[0];value=StockDialog(self.root,self.store,self.stock[index]).show()
        if value:self.stock[index]=value;self.refresh_stock()

    def remove_stock(self):
        selected=self.stock_list.curselection()
        if selected:self.stock.pop(selected[0]);self.refresh_stock()

    def preset(self,kinds):
        self.stock.extend(dict(kind=k,amount=3 if k in ('food','med','rad','parts','fragments','repairkit','ammo') else 1,chance=1,rarity_min=0,rarity_max=4) for k in kinds)
        self.refresh_stock()

    def commit(self):
        if not self.current:return True
        try:
            value=dict(self.entries[self.current],name=self.name.get().strip(),npc=self.npc.get().strip(),npc_art=self.art.get(),location_art=self.location_art.get(),
                       role=next(k for k,v in rules.ROLES.items() if v==self.role.get()),refresh_turns=int(self.refresh_turns.get()),stock=copy.deepcopy(self.stock))
            errors=rules.validate({self.current:value},self.store.art,self.store.data['equipment'],self.store.data['modules'],self.store.data['consumables'])
            if errors:raise ValueError('\n'.join(errors))
            self.entries[self.current]=value;return True
        except (ValueError,StopIteration) as exc:messagebox.showerror('Особливі локації',str(exc),parent=self.root);return False

    def add(self):
        if not self.commit():return
        if len(self.entries)>=32:messagebox.showerror('Особливі локації','На мапі підтримується до 32 локацій.',parent=self.root);return
        name=simpledialog.askstring('Нова локація','Назва локації:',parent=self.root)
        if not name or not name.strip():return
        n=1
        while f'site_custom_{n:03}' in self.entries:n+=1
        ident=f'site_custom_{n:03}'
        self.entries[ident]=dict(name=name.strip(),npc='Мешканець',npc_art='npc:mayor',role='quest',refresh_turns=100,stock=[])
        self.open(ident);self.rebuild()

    def delete(self):
        if not self.current:return
        if not messagebox.askyesno('Видалити локацію','Видалити цю локацію з каталогу для нових ігор?',parent=self.root):return
        del self.entries[self.current];self.current=None
        if self.entries:self.open(next(iter(self.entries)))
        else:
            for field in (self.ident,self.name,self.npc,self.art,self.location_art,self.role,self.refresh_turns):field.set('')
            self.stock=[];self.refresh_stock();self.show_art()
        self.rebuild()
