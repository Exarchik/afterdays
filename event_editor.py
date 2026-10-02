"""Ukrainian Tk editor for the shared road-event catalog; standard library only."""
import argparse
import copy
import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import event_catalog as catalog
import sprites


def row(parent, label, variable, values=None, readonly=False):
    frame = ttk.Frame(parent); frame.pack(fill='x', pady=4)
    ttk.Label(frame, text=label, width=24).pack(side='left')
    if values is not None:
        widget = ttk.Combobox(frame, textvariable=variable, values=values, state='readonly')
    else:
        widget = ttk.Entry(frame, textvariable=variable, state='readonly' if readonly else 'normal')
    widget.pack(side='left', fill='x', expand=True)
    return widget


class Dialog(tk.Toplevel):
    def __init__(self, parent, title, geometry='720x620'):
        super().__init__(parent)
        self.title(title); self.geometry(geometry); self.transient(parent)
        self.result = None
        self.protocol('WM_DELETE_WINDOW', self.destroy)
        self.body = ttk.Frame(self, padding=14); self.body.pack(fill='both', expand=True)
        self.buttons = ttk.Frame(self, padding=12); self.buttons.pack(fill='x')
        ttk.Button(self.buttons, text='Скасувати', command=self.destroy).pack(side='right', padx=5)
        ttk.Button(self.buttons, text='Застосувати', command=self.accept).pack(side='right')
        self.bind('<Escape>', lambda e: self.destroy())

    def show(self):
        self.wait_visibility(); self.grab_set(); self.wait_window()
        # Nested dialogs must restore their parent's modal grab.
        if isinstance(self.master, Dialog) and self.master.winfo_exists(): self.master.grab_set()
        return self.result

    def accept(self):
        try: self.result = self.read()
        except (ValueError, KeyError, TypeError) as exc:
            messagebox.showerror('Перевірте значення', str(exc), parent=self); return
        self.destroy()


class EffectDialog(Dialog):
    def __init__(self, parent, effect=None, cost=False, cache=False):
        super().__init__(parent, 'Витрата' if cost else 'Нагорода / наслідок', '730x670')
        self.original = copy.deepcopy(effect or {}); self.cost = cost
        kinds = catalog.COSTS if cost else tuple(k for k in catalog.EFFECTS if not cache or k in catalog.ITEM_KINDS | {'gear'})
        self.labels = {catalog.EFFECTS[k][0]: k for k in kinds}
        self.kind = tk.StringVar(value=catalog.EFFECTS[self.original.get('kind', kinds[0])][0])
        box = row(self.body, 'Тип', self.kind, list(self.labels)); box.bind('<<ComboboxSelected>>', self.explain)
        self.help = ttk.Label(self.body, wraplength=660, foreground='#426547'); self.help.pack(fill='x', pady=10)
        self.values = {}
        self.duration = tk.StringVar(value=str(self.original.get('duration',10)))
        fields = [('amount', 'Кількість / мінімум', 1)]
        if not cost: fields += [('maximum', 'Максимум (необов’язково)', ''), ('per_level', 'Додати за кожен рівень L', 0),
                               ('step', 'Додати 1 кожні N рівнів', 0), ('step_cap', 'Ліміт добавки кожні N', 0),
                               ('chance', 'Шанс ефекту, %', 100)]
        for key, label, default in fields:
            value = self.original.get(key, default)
            if key == 'chance': value = self.original.get('chance', 1)*100
            var = tk.StringVar(value=str(value)); self.values[key] = var; row(self.body, label, var)
        self.ammo = tk.StringVar(value=self.original.get('ammo', 'random'))
        self.destination = tk.StringVar(value='Рюкзак' if self.original.get('destination') == 'bag' else 'Здобич')
        if not cost:
            self.duration_field=row(self.body, 'Тривалість, кроків', self.duration)
            row(self.body, 'Тип набоїв (лише набої)', self.ammo, catalog.AMMO)
            row(self.body, 'Куди додати предмет', self.destination, ['Здобич', 'Рюкзак'])
            ttk.Label(self.body, text='L — рівень місцевості. Формула: кількість + добавка×L +\nmin(ліміт, ⌊(L−1)/N⌋). N=0 вимикає останню добавку.\nВід’ємні предмети / кредити — втрата наявного. Шкода задається додатним числом.',
                      wraplength=660).pack(fill='x', pady=12)
        self.explain()

    def explain(self, event=None):
        kind=self.labels[self.kind.get()]
        self.help.configure(text=catalog.EFFECTS[kind][1])
        if hasattr(self,'duration_field'):self.duration_field.configure(state='normal' if kind in catalog.TIMED_EFFECTS else 'disabled')

    def read(self):
        result = {'kind': self.labels[self.kind.get()], 'amount': int(self.values['amount'].get())}
        if self.cost:
            if result['amount'] <= 0: raise ValueError('Витрата має бути додатною.')
            return result
        for field in ('maximum', 'per_level', 'step', 'step_cap'):
            text = self.values[field].get().strip()
            if text: result[field] = int(text)
        result['chance'] = float(self.values['chance'].get())/100
        if not 0 <= result['chance'] <= 1: raise ValueError('Шанс має бути від 0 до 100%.')
        if result.get('maximum', result['amount']) < result['amount']: raise ValueError('Максимум менший за мінімум.')
        if result.get('step', 0) < 0 or result.get('step_cap', 0) < 0: raise ValueError('Крок і ліміт мають бути ≥ 0.')
        if result['kind'] not in catalog.ITEM_KINDS | {'money'} and (result['amount'] < 0 or result.get('per_level', 0) < 0):
            raise ValueError('Для цього ефекту задайте додатну кількість або нуль.')
        if result['kind'] == 'ammo': result['ammo'] = self.ammo.get()
        if result['kind'] in catalog.TIMED_EFFECTS:
            result['duration']=int(self.duration.get())
            if not 1<=result['duration']<=1000000:raise ValueError('Тривалість бафа: 1–1000000 кроків.')
        result['destination'] = 'bag' if self.destination.get() == 'Рюкзак' else 'loot'
        return result


class EffectList(ttk.Frame):
    def __init__(self, parent, title, cost=False, cache=False):
        super().__init__(parent)
        self.rows = []; self.cost = cost; self.cache = cache
        ttk.Label(self, text=title).pack(anchor='w', pady=5)
        self.list = tk.Listbox(self, height=6, exportselection=False)
        self.list.pack(fill='both', expand=True)
        self.list.bind('<Double-1>', lambda e: self.edit())
        bar = ttk.Frame(self); bar.pack(fill='x', pady=5)
        for label, command in [('Додати', self.add), ('Змінити', self.edit), ('Прибрати', self.remove), ('↑', lambda: self.move(-1)), ('↓', lambda: self.move(1))]:
            ttk.Button(bar, text=label, command=command, width=11 if len(label)>1 else 3).pack(side='left', padx=2)

    def set(self, rows): self.rows = copy.deepcopy(rows); self.refresh()
    def refresh(self):
        self.list.delete(0, 'end')
        for effect in self.rows: self.list.insert('end', catalog.describe(effect))
    def index(self): return self.list.curselection()[0] if self.list.curselection() else None
    def add(self):
        value = EffectDialog(self.winfo_toplevel(), cost=self.cost, cache=self.cache).show()
        if value is not None: self.rows.append(value); self.refresh()
    def edit(self):
        i = self.index()
        if i is None: return
        value = EffectDialog(self.winfo_toplevel(), self.rows[i], self.cost, self.cache).show()
        if value is not None: self.rows[i] = value; self.refresh(); self.list.selection_set(i)
    def remove(self):
        i = self.index()
        if i is not None: self.rows.pop(i); self.refresh()
    def move(self, delta):
        i = self.index()
        if i is not None and 0 <= i+delta < len(self.rows):
            self.rows[i], self.rows[i+delta] = self.rows[i+delta], self.rows[i]
            self.refresh(); self.list.selection_set(i+delta)


class OutcomeDialog(Dialog):
    def __init__(self, parent, outcome=None):
        super().__init__(parent, 'Можливий результат', '800x520')
        outcome = outcome or {'chance': 1, 'effects': []}
        self.chance = tk.StringVar(value=f"{outcome['chance']*100:g}")
        row(self.body, 'Шанс результату, %', self.chance)
        ttk.Label(self.body, text='Для однієї дії сума шансів усіх результатів має дорівнювати 100%.\nЕфекти виконуються згори вниз. Порожній результат означає відсутність наслідків.').pack(anchor='w', pady=10)
        self.effects = EffectList(self.body, 'Нагороди та штрафи'); self.effects.pack(fill='both', expand=True)
        self.effects.set(outcome.get('effects', []))
    def read(self):
        chance = float(self.chance.get())/100
        if not 0 <= chance <= 1: raise ValueError('Шанс має бути від 0 до 100%.')
        return dict(chance=chance, effects=copy.deepcopy(self.effects.rows))


class ChoiceDialog(Dialog):
    def __init__(self, parent, choice=None):
        super().__init__(parent, 'Дія гравця', '880x730')
        self.choice = copy.deepcopy(choice or dict(id='act', text='Дослідити', costs=[], outcomes=[dict(chance=1, effects=[])]))
        self.ident = tk.StringVar(value=self.choice['id']); self.text = tk.StringVar(value=self.choice['text'])
        row(self.body, 'ID дії', self.ident); row(self.body, 'Текст кнопки', self.text)
        ttk.Label(self.body, text='На кнопці у грі буде лише цей текст. Наслідки налаштовуються нижче.').pack(anchor='w', pady=5)
        self.costs = EffectList(self.body, 'Обов’язкова витрата перед вибором результату', cost=True)
        self.costs.pack(fill='x'); self.costs.set(self.choice.get('costs', []))
        ttk.Label(self.body, text='Можливі результати (сумарно 100%)').pack(anchor='w', pady=(12, 5))
        self.outcomes = tk.Listbox(self.body, height=6, exportselection=False); self.outcomes.pack(fill='both', expand=True)
        self.outcomes.bind('<Double-1>', lambda e: self.edit_outcome())
        bar = ttk.Frame(self.body); bar.pack(fill='x', pady=5)
        for text, command in [('Додати результат', self.add_outcome), ('Змінити', self.edit_outcome), ('Прибрати', self.remove_outcome)]:
            ttk.Button(bar, text=text, command=command).pack(side='left', padx=3)
        self.refresh()
    def refresh(self):
        self.outcomes.delete(0, 'end')
        for result in self.choice['outcomes']:
            text = ', '.join(catalog.describe(e) for e in result['effects']) or 'Без наслідків'
            self.outcomes.insert('end', f"{result['chance']*100:g}% — {text}")
    def add_outcome(self):
        value = OutcomeDialog(self).show()
        if value is not None: self.choice['outcomes'].append(value); self.refresh()
    def edit_outcome(self):
        if not self.outcomes.curselection(): return
        i = self.outcomes.curselection()[0]; value = OutcomeDialog(self, self.choice['outcomes'][i]).show()
        if value is not None: self.choice['outcomes'][i] = value; self.refresh()
    def remove_outcome(self):
        if self.outcomes.curselection(): self.choice['outcomes'].pop(self.outcomes.curselection()[0]); self.refresh()
    def read(self):
        import re
        if not re.fullmatch('[a-z][a-z0-9_]*', self.ident.get()): raise ValueError('ID: латинські малі літери, цифри й підкреслення.')
        if not self.text.get().strip(): raise ValueError('Додайте текст кнопки.')
        if abs(sum(o['chance'] for o in self.choice['outcomes'])-1) > 1e-8: raise ValueError('Сума шансів результатів має бути 100%.')
        self.choice.update(id=self.ident.get(), text=self.text.get().strip(), costs=copy.deepcopy(self.costs.rows))
        return self.choice


class ArtDialog(Dialog):
    def __init__(self, parent, current):
        super().__init__(parent, 'Зображення з асетів', '900x750')
        library=getattr(self._root(),'_editor_art_library',None)
        self.art=library.entries if library is not None else catalog.art_catalog()
        self.keys = sorted(self.art, key=lambda k: (not k.startswith('event_theme:'), k))
        self.selected = current; self.page = 0
        self.query = tk.StringVar(); row(self.body, 'Пошук за назвою асета', self.query)
        self.query.trace_add('write', self.filter)
        self.caption = ttk.Label(self.body, text=''); self.caption.pack(fill='x', pady=5)
        self.grid = ttk.Frame(self.body); self.grid.pack(fill='both', expand=True)
        bar = ttk.Frame(self.body); bar.pack(fill='x')
        ttk.Button(bar, text='← Назад', command=lambda: self.turn(-1)).pack(side='left')
        ttk.Button(bar, text='Далі →', command=lambda: self.turn(1)).pack(side='right')
        self.render()
    def filter(self, *args): self.page = 0; self.render()
    def turn(self, delta):
        pages = max(1, (len(self.filtered())+19)//20)
        self.page = max(0, min(pages-1, self.page+delta)); self.render()
    def filtered(self): return [k for k in self.keys if self.query.get().casefold() in (k+' '+self.art[k].get('art_label','')).casefold()]
    def pick(self, key): self.selected = key; self.render()
    def render(self):
        for child in self.grid.winfo_children(): child.destroy()
        keys = self.filtered(); self.images = []
        self.caption.configure(text=f'Обрано: {self.selected}    |    {len(keys)} асетів · сторінка {self.page+1}/{max(1,(len(keys)+19)//20)}')
        for i, key in enumerate(keys[self.page*20:(self.page+1)*20]):
            image = sprites.photo(self, key, 96); self.images.append(image)
            cell = ttk.Frame(self.grid)
            cell.grid(row=i//5, column=i%5, sticky='nsew', padx=3, pady=3)
            ttk.Button(cell, image=image or '', command=lambda k=key: self.pick(k)).pack(fill='x')
            label = ttk.Label(cell, text=('✓ ' if key == self.selected else '')+self.art[key].get('art_label',key), wraplength=152, anchor='center')
            label.pack(fill='x'); label.bind('<Button-1>', lambda e,k=key: self.pick(k))
        for col in range(5): self.grid.columnconfigure(col, weight=1, uniform='art')
    def read(self): return self.selected


class Editor(ttk.Frame):
    def __init__(self, root, path=catalog.PATH, embedded=False):
        super().__init__(root, padding=10); self.pack(fill='both', expand=True)
        root=self.winfo_toplevel()
        self.root = root; self.path = Path(path)
        library=getattr(root,'_editor_art_library',None)
        self.document = catalog.load(self.path,art=library.entries if library else None)
        self.baseline = copy.deepcopy(self.document); self.disk = self.path.read_bytes()
        self.current = None; self.loading = False
        if not embedded:
            root.title('Afterdays — редактор випадкових подій'); root.geometry('1220x800'); root.minsize(1000, 700)
            root.protocol('WM_DELETE_WINDOW', self.close); root.bind('<Control-s>', lambda e: self.save())
        bar = ttk.Frame(self); bar.pack(fill='x', pady=(0, 10))
        ttk.Label(bar, text='Випадкові події', font=('Segoe UI', 18, 'bold')).pack(side='left')
        ttk.Button(bar, text='Зберегти каталог · Ctrl+S', command=self.save).pack(side='right')
        ttk.Button(bar, text='Нова подія', command=self.new).pack(side='right', padx=8)
        ttk.Button(bar, text='Дублювати', command=self.duplicate).pack(side='right')
        split = ttk.Panedwindow(self, orient='horizontal'); split.pack(fill='both', expand=True)
        left = ttk.Frame(split, width=320); split.add(left, weight=1)
        right = ttk.Frame(split, padding=(12,0,0,0)); split.add(right, weight=3)
        self.query = tk.StringVar(); ttk.Entry(left, textvariable=self.query).pack(fill='x', pady=(0,6))
        ttk.Label(left, text='Пошук за назвою, ID або описом').pack(anchor='w')
        self.tree = ttk.Treeview(left, show='tree', selectmode='browse'); self.tree.pack(fill='both', expand=True, pady=6)
        self.tree.bind('<<TreeviewSelect>>', self.select); self.query.trace_add('write', self.filter)
        self.book = ttk.Notebook(right); self.book.pack(fill='both', expand=True)
        general = ttk.Frame(self.book, padding=12); actions = ttk.Frame(self.book, padding=12)
        cache = ttk.Frame(self.book, padding=12); help_tab = ttk.Frame(self.book, padding=12)
        for frame, label in [(general, 'Опис і зображення'), (actions, 'Дії та результати'), (cache, 'Сховок'), (help_tab, 'Довідка ефектів')]: self.book.add(frame, text=label)
        self.fields = {k: tk.StringVar() for k in ('id','title','category','terrain','weight','art')}
        row(general, 'Сталий ID', self.fields['id'], readonly=True)
        row(general, 'Назва', self.fields['title'])
        row(general, 'Категорія', self.fields['category'], list(catalog.CATEGORIES.values()))
        row(general, 'Місцевість', self.fields['terrain'], list(catalog.TERRAINS.values()))
        row(general, 'Вага випадкового вибору', self.fields['weight'])
        self.enabled = tk.BooleanVar(); ttk.Checkbutton(general, text='Подія активна (вимкніть, щоб прибрати з випадкового вибору)', variable=self.enabled).pack(anchor='w', pady=5)
        ttk.Label(general, text='Опис ситуації').pack(anchor='w', pady=(12,4))
        self.description = tk.Text(general, height=5, wrap='word', font=('Segoe UI', 11), undo=True)
        self.description.pack(fill='x')
        picture = ttk.Frame(general); picture.pack(fill='both', expand=True, pady=12)
        self.picture = ttk.Label(picture); self.picture.pack(side='left', padx=(0,18))
        art_controls = ttk.Frame(picture); art_controls.pack(side='left', fill='x', expand=True)
        ttk.Label(art_controls, textvariable=self.fields['art'], wraplength=350).pack(anchor='w', pady=10)
        ttk.Button(art_controls, text='Вибрати зображення з асетів…', command=self.choose_art).pack(anchor='w')
        ttk.Label(art_controls, text='Усі зареєстровані спрайти й ілюстрації.\nОбране зображення використовується у грі.', wraplength=350).pack(anchor='w', pady=10)
        ttk.Label(actions, text='Кожна дія має витрати й один або декілька результатів.\nУ грі кнопка показує лише «Текст кнопки»; подробиці нижче — для редактора.').pack(anchor='w', pady=6)
        self.choices = []; self.choice_list = tk.Listbox(actions, height=9, exportselection=False)
        self.choice_list.pack(fill='x', pady=10); self.choice_list.bind('<Double-1>', lambda e: self.edit_choice())
        self.choice_list.bind('<<ListboxSelect>>', lambda e: self.preview_choice())
        buttonbar = ttk.Frame(actions); buttonbar.pack(fill='x')
        for label, command in [('Додати дію', self.add_choice), ('Змінити', self.edit_choice), ('Прибрати', self.remove_choice), ('↑', lambda: self.move_choice(-1)), ('↓', lambda: self.move_choice(1))]:
            ttk.Button(buttonbar, text=label, command=command).pack(side='left', padx=3)
        self.choice_preview = tk.Text(actions, height=12, wrap='word', font=('Segoe UI', 11), state='disabled')
        self.choice_preview.pack(fill='both', expand=True, pady=15)
        ttk.Label(cache, text='Лише для подій з ефектом «Відкрити замок». Предмети генеруються\nодин раз на рівні місцевості L; повторний злам не змінює здобич.\nНевдала спроба витрачає 1 запчастину.').pack(anchor='w', pady=10)
        self.cache = EffectList(cache, 'Предмети всередині сховку', cache=True); self.cache.pack(fill='both', expand=True)
        help_text = tk.Text(help_tab, wrap='word', font=('Segoe UI', 11)); help_text.pack(fill='both', expand=True)
        help_text.insert('end', 'Редагування без коду\n\n1. Оберіть подію або створіть нову.\n2. Змініть опис, місцевість і зображення.\n3. На вкладці дій задайте витрати, результати та їхні шанси.\n4. Збережіть каталог і перезапустіть гру.\n\nВага 2 означає удвічі частіший вибір, ніж вага 1, серед доступних подій тієї ж місцевості. Категорія лише впорядковує список.\n\nXP — кінцева нагорода без прихованого перерахунку. Чинний штраф боягузтва лишається.\n\nID наявних подій не змінюються. Для вилучення з гри вимкніть подію. Уже відкриті події та сховки в збереженні зберігають свої нагороди.\n\n')
        for name, description in catalog.EFFECTS.values(): help_text.insert('end', name+'\n'+description+'\n\n')
        help_text.configure(state='disabled')
        self.status = tk.StringVar(value=f'{len(self.document["events"])} подій · Зміни набудуть чинності після перезапуску гри')
        ttk.Label(self, textvariable=self.status).pack(fill='x', pady=(8,0))
        self.rebuild()
        if self.document['events']: self.open_event(catalog.ordered(self.document['events'])[0]['id'])

    def lookup(self, ident): return next(e for e in self.document['events'] if e['id'] == ident)
    def rebuild(self):
        self.loading = True
        self.tree.delete(*self.tree.get_children()); query = self.query.get().casefold()
        for event in catalog.ordered(self.document['events']):
            if query and query not in ' '.join((event['id'], event['title'], event['description'])).casefold(): continue
            group = 'group:'+event['category']; terrain = group+':'+event['terrain']
            if not self.tree.exists(group): self.tree.insert('', 'end', iid=group, text=catalog.CATEGORIES[event['category']], open=True)
            if not self.tree.exists(terrain): self.tree.insert(group, 'end', iid=terrain, text=catalog.TERRAINS[event['terrain']], open=True)
            self.tree.insert(terrain, 'end', iid=event['id'], text=('○ ' if not event['enabled'] else '')+event['title'])
        if self.current and self.tree.exists(self.current): self.tree.selection_set(self.current)
        self.loading = False
    def filter(self, *args):
        if self.commit(): self.rebuild()
    def commit(self):
        if self.current is None: return True
        try:
            event = copy.deepcopy(self.lookup(self.current))
            event.update(title=self.fields['title'].get().strip(), description=self.description.get('1.0','end-1c').strip(),
                         category=next(k for k,v in catalog.CATEGORIES.items() if v == self.fields['category'].get()),
                         terrain=next(k for k,v in catalog.TERRAINS.items() if v == self.fields['terrain'].get()),
                         weight=float(self.fields['weight'].get()), enabled=self.enabled.get(), art=self.fields['art'].get(), choices=copy.deepcopy(self.choices))
            if self.cache.rows: event['cache'] = copy.deepcopy(self.cache.rows)
            else: event.pop('cache', None)
            library=getattr(self.root,'_editor_art_library',None)
            errors = catalog.validate({'version':1, 'events':[event]},art=library.entries if library else None)
            if errors: raise ValueError('\n'.join(errors))
            self.lookup(self.current).update(event)
            if 'cache' not in event: self.lookup(self.current).pop('cache', None)
            return True
        except (ValueError, StopIteration) as exc:
            messagebox.showerror('Подію не застосовано', str(exc), parent=self.root); return False
    def select(self, event=None):
        if self.loading or not self.tree.selection(): return
        ident = self.tree.selection()[0]
        if ident.startswith('group:') or ident == self.current: return
        if self.commit(): self.open_event(ident)
        elif self.current and self.tree.exists(self.current): self.tree.selection_set(self.current)
    def open_event(self, ident):
        event = self.lookup(ident); self.current = ident
        for k in ('id','title','art','weight'): self.fields[k].set(str(event[k]))
        self.fields['category'].set(catalog.CATEGORIES[event['category']]); self.fields['terrain'].set(catalog.TERRAINS[event['terrain']])
        self.enabled.set(event['enabled']); self.description.delete('1.0','end'); self.description.insert('1.0',event['description'])
        self.choices = copy.deepcopy(event['choices']); self.refresh_choices(); self.cache.set(event.get('cache', [])); self.refresh_art()
        if self.tree.exists(ident): self.tree.selection_set(ident); self.tree.see(ident)
    def refresh_art(self):
        self.image = sprites.photo(self.root, self.fields['art'].get(), 144)
        self.picture.configure(image=self.image or '', text='' if self.image else 'Зображення недоступне')
    def choose_art(self):
        value = ArtDialog(self.root, self.fields['art'].get()).show()
        if value is not None: self.fields['art'].set(value); self.refresh_art()
    def refresh_choices(self):
        self.choice_list.delete(0, 'end')
        for choice in self.choices: self.choice_list.insert('end', choice['text']+' ['+choice['id']+']')
        if self.choices: self.choice_list.selection_set(0)
        self.preview_choice()
    def preview_choice(self):
        self.choice_preview.configure(state='normal'); self.choice_preview.delete('1.0','end')
        if self.choice_list.curselection():
            choice = self.choices[self.choice_list.curselection()[0]]
            self.choice_preview.insert('end', catalog.choice_text(choice))
        self.choice_preview.configure(state='disabled')
    def add_choice(self):
        existing = {c['id'] for c in self.choices}; n = 1
        while 'act_'+str(n) in existing: n += 1
        value = ChoiceDialog(self.root, dict(id='act_'+str(n), text='Нова дія', costs=[], outcomes=[dict(chance=1,effects=[])])).show()
        if value is not None:
            if value['id'] in existing: messagebox.showerror('ID зайнято', 'Дія з таким ID вже існує.', parent=self.root); return
            self.choices.append(value); self.refresh_choices()
    def edit_choice(self):
        if not self.choice_list.curselection(): return
        i = self.choice_list.curselection()[0]; value = ChoiceDialog(self.root, self.choices[i]).show()
        if value is not None:
            if any(c['id'] == value['id'] for j,c in enumerate(self.choices) if j != i):
                messagebox.showerror('ID зайнято', 'Дія з таким ID вже існує.', parent=self.root); return
            self.choices[i] = value; self.refresh_choices(); self.choice_list.selection_clear(0,'end'); self.choice_list.selection_set(i); self.preview_choice()
    def remove_choice(self):
        if self.choice_list.curselection(): self.choices.pop(self.choice_list.curselection()[0]); self.refresh_choices()
    def move_choice(self, delta):
        if not self.choice_list.curselection(): return
        i = self.choice_list.curselection()[0]
        if 0 <= i+delta < len(self.choices):
            self.choices[i], self.choices[i+delta] = self.choices[i+delta], self.choices[i]
            self.refresh_choices(); self.choice_list.selection_clear(0,'end'); self.choice_list.selection_set(i+delta); self.preview_choice()
    def next_id(self):
        n = 1; ids = {e['id'] for e in self.document['events']}
        while f'event_{n:03}' in ids: n += 1
        return f'event_{n:03}'
    def new(self):
        if not self.commit(): return
        title = simpledialog.askstring('Нова подія', 'Назва події:', parent=self.root)
        if not title or not title.strip(): return
        event = dict(id=self.next_id(), title=title.strip(), description='Опишіть, що побачив гравець.', category='exploration', terrain='any', enabled=True, weight=1, art='event_theme:camp',
                     choices=[dict(id='act',text='Дослідити',costs=[],outcomes=[dict(chance=1,effects=[])]),dict(id='leave',text='Пройти повз',costs=[],outcomes=[dict(chance=1,effects=[])])])
        self.document['events'].append(event); self.query.set(''); self.rebuild(); self.open_event(event['id']); self.book.select(0)
    def duplicate(self):
        if not self.current or not self.commit(): return
        event = copy.deepcopy(self.lookup(self.current)); event['id'] = self.next_id(); event['title'] += ' (копія)'; event.pop('legacy_group',None)
        self.document['events'].append(event); self.query.set(''); self.rebuild(); self.open_event(event['id'])
    def save(self):
        if getattr(self,'save_handler',None):return self.save_handler()
        if not self.commit(): return False
        try:
            if self.path.read_bytes() != self.disk:
                raise ValueError('Каталог змінено іншою програмою. Збереження зупинено, щоб не затерти її зміни. Закрийте й відкрийте редактор повторно.')
            catalog.save(self.document, self.path)
            self.disk = self.path.read_bytes(); self.baseline = copy.deepcopy(self.document)
        except (OSError, ValueError) as exc:
            messagebox.showerror('Не вдалося зберегти', str(exc), parent=self.root); return False
        self.rebuild(); self.status.set(f'Збережено {len(self.document["events"])} подій · Резервна копія: {self.path.name}.bak · Перезапустіть гру')
        return True
    def close(self):
        if not self.commit():
            if messagebox.askyesno('Незбережені зміни', 'Закрити редактор і відкинути незбережені зміни?', parent=self.root): self.root.destroy()
            return
        if self.document != self.baseline:
            answer = messagebox.askyesnocancel('Незбережені зміни', 'Зберегти зміни перед закриттям?', parent=self.root)
            if answer is None or (answer and not self.save()): return
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, default=catalog.PATH)
    parser.add_argument('--check', action='store_true', help='Validate without opening a window')
    args = parser.parse_args()
    if args.check:
        from entity_catalog import Store
        doc = catalog.load(args.catalog); errors=Store().validate()
        if errors: raise ValueError('\n'.join(errors))
        print(f"OK: {len(doc['events'])} events; equipment, modules, monsters"); return
    root = tk.Tk()
    try:
        from content_editor import ContentEditor
        ttk.Style(root).theme_use('clam'); ContentEditor(root, args.catalog); root.mainloop()
    except (OSError, ValueError) as exc:
        messagebox.showerror('Каталог подій', str(exc), parent=root); root.destroy()


if __name__ == '__main__': main()
