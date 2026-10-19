"""Editable regular/elite profiles for every built-in quest family."""
import copy
import tkinter as tk
from tkinter import ttk,messagebox
import quest_profiles as profiles

class NativeQuestForm(ttk.Frame):
    def __init__(self,parent,store):
        super().__init__(parent);self.store=store;self.kind=None;self.variant='normal';self.loading=False
        self.variant_var=tk.StringVar(value='Звичайний')
        variant=ttk.Combobox(self,textvariable=self.variant_var,values=['Звичайний','Елітний'],state='readonly')
        variant.pack(anchor='w',pady=6);variant.bind('<<ComboboxSelected>>',self.switch)
        form=ttk.Frame(self);form.pack(fill='x');form.columnconfigure(1,weight=1)
        self.vars={}
        fields=[('title','Назва',str),('art','ID арту',str),('min_level','Мінімальний рівень гравця',int),
                ('reward','Базові кредити (рівень 1)',int),('money_power','Степінь рівня для кредитів',float),
                ('xp_reward','Базовий XP (рівень 1)',int),('xp_step','XP за кожен наступний рівень',int)]
        self.fields=fields
        for n,(key,label,kind) in enumerate(fields):
            ttk.Label(form,text=label).grid(row=n,column=0,sticky='w',pady=4)
            self.vars[key]=tk.StringVar()
            ttk.Entry(form,textvariable=self.vars[key]).grid(row=n,column=1,sticky='ew',padx=6)
            self.vars[key].trace_add('write',lambda *_:self.preview())
        ttk.Button(form,text='Вибрати арт…',command=self.pick_art).grid(row=1,column=2)
        # Minigame settings, shown only for quest types that have them.
        from game.systems.radiation_source import SETTINGS
        self.extra=ttk.LabelFrame(self,text='Мінігра «Дозиметр»',padding=6);self.extra.columnconfigure(1,weight=1)
        self.extra_fields=[('grid_size','Розмір ділянки, гексів по стороні',SETTINGS['grid_size']),
                           ('max_dose','Радіація за замір біля джерела',SETTINGS['max_dose']),
                           ('device_radiation','Радіація від приладу за крок',SETTINGS['device_radiation'])]
        for n,(key,label,(default,low,high)) in enumerate(self.extra_fields):
            ttk.Label(self.extra,text=f'{label} ({low}–{high})').grid(row=n,column=0,sticky='w',pady=3)
            self.vars[key]=tk.StringVar()
            ttk.Entry(self.extra,textvariable=self.vars[key],width=8).grid(row=n,column=1,sticky='w',padx=6)
        row=len(self.extra_fields)
        ttk.Label(self.extra,text='Арт приладу (порожньо — стандартна іконка)').grid(row=row,column=0,sticky='w',pady=3)
        self.vars['device_art']=tk.StringVar()
        art_row=ttk.Frame(self.extra);art_row.grid(row=row,column=1,sticky='ew',padx=6)
        ttk.Entry(art_row,textvariable=self.vars['device_art']).pack(side='left',fill='x',expand=True)
        ttk.Button(art_row,text='Вибрати…',command=self.pick_device_art).pack(side='left',padx=(6,0))
        ttk.Label(self.extra,text='Заміри без обмежень: гравець шукає, доки не заміряє сам гекс із джерелом. Єдина ціна довгого пошуку — накопичена радіація.\n'
                  'Після знахідки гравець несе радіоактивний прилад замовнику; радіопротектор блокує опромінення від нього.',
                  wraplength=600,justify='left').grid(row=row+1,column=0,columnspan=2,sticky='w',pady=(4,0))
        self.extra_anchor=form
        self.art_canvas=tk.Canvas(self,width=96,height=96,highlightthickness=0);self.art_canvas.pack(anchor='w',pady=5)
        ttk.Label(self,text='Опис (додається до конкретних цілей та прогресу квесту)').pack(anchor='w')
        self.description=tk.Text(self,height=5,wrap='word');self.description.pack(fill='x')
        self.summary=ttk.Label(self,justify='left',wraplength=650,font=('Consolas',10));self.summary.pack(fill='x',pady=10)
        ttk.Label(self,text='Кредити = база × рівень^степінь. XP = база + приріст × (рівень − 1).\n'
                  'Таблиця показує базові нагороди: гра окремо враховує репутацію та компенсацію їжі/медикаментів/трофеїв.\n'
                  'XP за квести нижчого рівня зменшується за чинними правилами. Звичайний та елітний варіанти налаштовуються незалежно.\n'
                  'Відновлення метро видається як елітний квест; дозвіл і подяка — як звичайні.\n'
                  'Зміни застосовуються до нових пропозицій. Умови вже прийнятих квестів зберігаються.',
                  wraplength=650,justify='left').pack(fill='x',pady=6)

    def open(self,kind):
        self.kind=kind;self.variant='elite' if kind=='metro' else 'normal'
        self.variant_var.set('Елітний' if self.variant=='elite' else 'Звичайний');self.load()

    def load(self):
        self.loading=True
        spec=self.store.data['quests'].get('native',{}).get(self.kind,{}).get(self.variant,profiles.defaults(self.kind,self.variant=='elite'))
        self.original=copy.deepcopy(spec)
        extra=self.kind=='radiation_source'
        if extra:
            from game.systems.radiation_source import settings_for
            spec=dict(spec,**{k:v for k,v in settings_for(spec).items() if k not in spec})
            spec.setdefault('device_art','')
            self.extra.pack(fill='x',pady=6,after=self.extra_anchor)
        else:self.extra.pack_forget()
        for key,var in self.vars.items():
            var.set(spec[key] if key in spec else '')
        self.description.delete('1.0','end');self.description.insert('1.0',spec['description'])
        self.loading=False;self.preview()

    def read(self):
        spec={key:kind(self.vars[key].get().strip()) for key,_,kind in self.fields}
        if self.kind=='radiation_source':
            for key,_,_ in self.extra_fields:spec[key]=int(self.vars[key].get().strip())
            spec['device_art']=self.vars['device_art'].get().strip()
        spec['description']=self.description.get('1.0','end-1c')
        return spec

    def commit(self):
        if self.kind is None:return True
        try:
            spec=self.read();errors=profiles.validate_spec(spec)
            if self.kind=='radiation_source':
                from game.systems.radiation_source import validate_settings
                errors+=validate_settings(spec)
                if spec['device_art'] and spec['device_art'] not in self.store.art:errors.append('Арт приладу не знайдено в бібліотеці')
            if spec['art'] and spec['art'] not in self.store.art:errors.append('ID арту не знайдено в бібліотеці')
            if errors:raise ValueError('\n'.join(errors))
            if spec!=self.original:
                self.store.data['quests'].setdefault('native',{}).setdefault(self.kind,{})[self.variant]=spec
                self.original=copy.deepcopy(spec)
            return True
        except ValueError as exc:
            messagebox.showerror('Некоректний квест',str(exc),parent=self);return False

    def switch(self,event=None):
        target='elite' if self.variant_var.get()=='Елітний' else 'normal'
        if not self.commit():self.variant_var.set('Елітний' if self.variant=='elite' else 'Звичайний');return
        self.variant=target;self.load()

    def pick_device_art(self):
        from event_editor import ArtDialog
        value=ArtDialog(self.winfo_toplevel(),self.vars['device_art'].get()).show()
        if value:self.vars['device_art'].set(value)

    def pick_art(self):
        from event_editor import ArtDialog
        value=ArtDialog(self.winfo_toplevel(),self.vars['art'].get()).show()
        if value:self.vars['art'].set(value)

    def preview(self):
        if self.loading or not self.kind:return
        try:
            spec=self.read()
            if profiles.validate_spec(spec):raise ValueError()
            self.summary.config(text='Рівень квесту     Кредити     XP\n'+'\n'.join(
                f'{level:>8}                  {profiles.rewards(spec,level)[0]:>7}      {profiles.rewards(spec,level)[1]}' for level in (1,2,5,10,20)))
        except (ValueError,OverflowError):self.summary.config(text='Введіть коректні числа для розрахунку нагород.')
        self.art_canvas.delete('all')
        library=getattr(self.winfo_toplevel(),'_editor_art_library',None)
        if library:
            photo=library.photo(self.art_canvas,self.vars['art'].get(),96)
        else:
            import sprites
            photo=sprites.photo(self.art_canvas,self.vars['art'].get(),96)
        self.photo=photo
        if photo:self.art_canvas.create_image(48,48,image=photo)
