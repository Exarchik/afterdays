"""Art library UI: import, crop, fit, rotate and replace sprites without editing JSON."""
import copy
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from event_editor import Dialog, row
import art_library as art
import sprites

FILE_TYPES=[('Зображення','*.png *.jpg *.jpeg *.webp *.bmp *.gif'),('Усі файли','*.*')]


class ImportedSourceDialog(Dialog):
    def __init__(self,parent,library):
        super().__init__(parent,'Вибрати з імпортованого','900x630')
        self.library=library;self.sources={r['path']:r for r in library.imported_sources()};self.images={}
        self.query=tk.StringVar();row(self.body,'Пошук назви / файлу',self.query)
        split=ttk.Frame(self.body);split.pack(fill='both',expand=True,pady=8)
        left=ttk.Frame(split);left.pack(side='left',fill='both',expand=True)
        ttk.Style(self).configure('ImportedSource.Treeview',rowheight=58)
        self.list=ttk.Treeview(left,show='tree',selectmode='browse',style='ImportedSource.Treeview')
        self.list.column('#0',width=410)
        scroll=ttk.Scrollbar(left,command=self.list.yview);scroll.pack(side='right',fill='y')
        self.list.configure(yscrollcommand=scroll.set);self.list.pack(fill='both',expand=True)
        right=ttk.Frame(split,width=290);right.pack(side='right',fill='y',padx=(16,0))
        self.preview=tk.Canvas(right,width=256,height=256,bg='#26382d',highlightthickness=0);self.preview.pack()
        self.info=tk.StringVar();ttk.Label(right,textvariable=self.info,wraplength=280).pack(fill='x',pady=12)
        self.status=tk.StringVar();ttk.Label(self.body,textvariable=self.status).pack(anchor='w')
        self.list.bind('<<TreeviewSelect>>',self.select)
        self.list.bind('<Double-1>',lambda e:self.accept() if self.list.selection() else None)
        self.query.trace_add('write',lambda *args:self.rebuild());self.rebuild()

    def photo(self,path,size):
        from PIL import Image,ImageTk
        image=self.library.image_file(path);image.thumbnail((size,size),Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(image,master=self)

    def rebuild(self):
        selected=self.list.selection();self.list.delete(*self.list.get_children());query=self.query.get().casefold()
        for path,entry in self.sources.items():
            if query not in (entry['name']+' '+path).casefold():continue
            try:
                if path not in self.images:self.images[path]=self.photo(path,48)
                image=self.images[path]
            except (OSError,ValueError):image=''
            self.list.insert('','end',iid=path,text=entry['name'],image=image)
        rows=self.list.get_children();self.status.set(f'Оригіналів: {len(rows)} із {len(self.sources)} · Вибір повторно використовує наявне зображення')
        if rows:self.list.selection_set(selected[0] if selected and selected[0] in rows else rows[0]);self.select()
        else:self.preview.delete('all');self.info.set('Немає імпортованих оригіналів.' if not self.sources else 'Нічого не знайдено.')

    def select(self,event=None):
        if not self.list.selection():return
        path=self.list.selection()[0];self.preview.delete('all')
        try:
            image=self.library.image_file(path);self.preview_photo=self.photo(path,244)
            self.preview.create_image(128,128,image=self.preview_photo)
            self.info.set(f"{self.sources[path]['name']}\n\n{image.width} × {image.height} px\n\n{Path(path).name}")
        except (OSError,ValueError) as exc:self.info.set('Не вдалося прочитати зображення: '+str(exc))

    def read(self):
        if not self.list.selection():raise ValueError('Виберіть початкове зображення.')
        path=self.list.selection()[0]
        try:self.library.image_file(path)
        except (OSError,ValueError) as exc:raise ValueError('Не вдалося прочитати оригінал: '+str(exc)) from exc
        return path


class ArtEditDialog(Dialog):
    def __init__(self,parent,source,name,group='other',settings=None):
        super().__init__(parent,'Редагування арту','1020x800')
        self.source=source;self.options=copy.deepcopy(settings or art.DEFAULTS);self.pending=None;self.drag=None
        self.name=tk.StringVar(value=name);self.group=tk.StringVar(value=art.GROUPS[group])
        row(self.body,'Назва у бібліотеці',self.name);row(self.body,'Категорія',self.group,list(art.GROUPS.values()))
        split=ttk.Frame(self.body);split.pack(fill='both',expand=True,pady=8)
        left=ttk.Frame(split);left.pack(side='left',fill='both',expand=True,padx=(0,16))
        right=ttk.Frame(split,width=340);right.pack(side='right',fill='y')
        ttk.Label(left,text='Початкове зображення · потягніть мишею, щоб обрізати').pack(anchor='w',pady=4)
        self.canvas=tk.Canvas(left,width=580,height=390,bg='#343c3b',highlightthickness=0)
        self.canvas.pack(fill='both',expand=True)
        self.canvas.bind('<Configure>',lambda e:self.draw_source())
        self.canvas.bind('<ButtonPress-1>',self.start_crop);self.canvas.bind('<B1-Motion>',self.drag_crop);self.canvas.bind('<ButtonRelease-1>',self.end_crop)
        self.source_info=tk.StringVar();ttk.Label(left,textvariable=self.source_info).pack(anchor='w',pady=5)
        bar=ttk.Frame(left);bar.pack(fill='x')
        ttk.Button(bar,text='Вибрати інший файл…',command=self.replace_source).pack(side='left',padx=3)
        ttk.Button(bar,text='Вибрати з імпортованого',command=self.choose_imported).pack(side='left',padx=3)
        ttk.Button(bar,text='Скинути обрізання',command=self.reset_crop).pack(side='left',padx=3)
        self.crop_enabled=tk.BooleanVar(value=self.options.get('crop') is not None)
        ttk.Checkbutton(left,text='Обрізати до вказаної області',variable=self.crop_enabled,command=self.changed).pack(anchor='w',pady=8)
        crop_frame=ttk.Frame(left);crop_frame.pack(fill='x')
        self.coords=[]
        crop=self.options.get('crop') or (0,0,source.width,source.height)
        for label,value in zip(('X₁','Y₁','X₂','Y₂'),crop):
            ttk.Label(crop_frame,text=label).pack(side='left',padx=3)
            var=tk.StringVar(value=str(value));self.coords.append(var)
            ttk.Entry(crop_frame,textvariable=var,width=7).pack(side='left');var.trace_add('write',lambda *a:self.changed())
        ttk.Label(right,text='У грі · 192 × 192',font=('Segoe UI',12,'bold')).pack(anchor='w')
        self.preview=tk.Canvas(right,width=192,height=192,bg='#495251',highlightthickness=0);self.preview.pack(pady=10)
        self.fit=tk.StringVar(value='Вписати повністю' if self.options['fit']=='contain' else 'Заповнити квадрат')
        row(right,'Підгонка',self.fit,['Вписати повністю','Заповнити квадрат'])
        self.padding=tk.StringVar(value=str(self.options['padding']));row(right,'Відступ, %',self.padding)
        self.rotation=tk.StringVar(value=str(self.options['rotation']));row(right,'Поворот, °',self.rotation,['0','90','180','270'])
        self.mirror=tk.BooleanVar(value=self.options['mirror']);self.trim=tk.BooleanVar(value=self.options['trim'])
        ttk.Checkbutton(right,text='Віддзеркалити по горизонталі',variable=self.mirror,command=self.changed).pack(anchor='w',pady=5)
        ttk.Checkbutton(right,text='Прибрати прозорі поля',variable=self.trim,command=self.changed).pack(anchor='w',pady=5)
        ttk.Label(right,text='В інвентарі · 96 × 72').pack(anchor='w',pady=(15,4))
        self.inventory=tk.Canvas(right,width=96,height=72,bg='#495251',highlightthickness=0);self.inventory.pack()
        ttk.Label(right,text='Прозорість зберігається. Буде створено всі 8 розмірів спрайта та 6 розмірів для інвентарю. Початковий файл лишається для повторного редагування.',wraplength=320).pack(pady=12)
        self.error=tk.StringVar();ttk.Label(self.body,textvariable=self.error,foreground='#a0392c',wraplength=960).pack(fill='x')
        for var in (self.fit,self.padding,self.rotation):var.trace_add('write',lambda *a:self.changed())
        self.draw_source();self.render()

    def settings(self):
        return dict(fit='contain' if self.fit.get()=='Вписати повністю' else 'cover',padding=float(self.padding.get()),
                    rotation=int(self.rotation.get()),mirror=self.mirror.get(),trim=self.trim.get(),
                    crop=[int(v.get()) for v in self.coords] if self.crop_enabled.get() else None)
    def draw_source(self):
        from PIL import Image,ImageTk
        w=max(100,self.canvas.winfo_width());h=max(100,self.canvas.winfo_height())
        pic=self.source.copy();pic.thumbnail((w-12,h-12),Image.Resampling.LANCZOS)
        self.offset=((w-pic.width)/2,(h-pic.height)/2);self.scale=(pic.width/self.source.width,pic.height/self.source.height)
        self.source_photo=ImageTk.PhotoImage(pic,master=self);self.canvas.delete('all')
        self.canvas.create_image(*self.offset,image=self.source_photo,anchor='nw')
        self.source_info.set(f'{self.source.width} × {self.source.height} px · перетягування виділяє область початкового зображення')
        self.draw_crop()
    def draw_crop(self):
        self.canvas.delete('crop')
        if not self.crop_enabled.get():return
        try:x,y,r,b=[int(v.get()) for v in self.coords]
        except ValueError:return
        ox,oy=self.offset;sx,sy=self.scale
        self.canvas.create_rectangle(ox+x*sx,oy+y*sy,ox+r*sx,oy+b*sy,outline='#64ead7',width=2,tags='crop')
    def source_point(self,event):
        ox,oy=self.offset;sx,sy=self.scale
        return (max(0,min(self.source.width,round((event.x-ox)/sx))),max(0,min(self.source.height,round((event.y-oy)/sy))))
    def start_crop(self,event):self.drag=self.source_point(event)
    def drag_crop(self,event):
        if self.drag is None:return
        x,y=self.source_point(event);a,b=self.drag
        if x==a or y==b:return
        self.crop_enabled.set(True)
        for var,value in zip(self.coords,(min(a,x),min(b,y),max(a,x),max(b,y))):var.set(str(value))
        self.draw_crop()
    def end_crop(self,event):self.drag_crop(event);self.drag=None;self.changed()
    def reset_crop(self):
        self.crop_enabled.set(False)
        for var,value in zip(self.coords,(0,0,self.source.width,self.source.height)):var.set(str(value))
        self.changed()
    def replace_source(self):
        path=filedialog.askopenfilename(parent=self,title='Зображення арту',filetypes=FILE_TYPES)
        if not path:return
        try:self.source=art.decode(path)
        except (OSError,ValueError) as exc:messagebox.showerror('Не вдалося відкрити',str(exc),parent=self);return
        self.reset_crop();self.draw_source();self.changed()
    def choose_imported(self):
        library=getattr(self._root(),'_editor_art_library',None)
        if library is None:return
        path=ImportedSourceDialog(self,library).show()
        if path is None:return
        try:self.source=library.image_file(path)
        except (OSError,ValueError) as exc:messagebox.showerror('Не вдалося відкрити',str(exc),parent=self);return
        self.drag=None;self.reset_crop();self.draw_source();self.changed()
    def changed(self):
        if self.pending:self.after_cancel(self.pending)
        self.pending=self.after(100,self.render)
    def render(self):
        self.pending=None
        try:
            from PIL import ImageTk
            settings=self.settings();self.preview_photo=ImageTk.PhotoImage(art.tile(self.source,settings,192),master=self)
            self.inventory_photo=ImageTk.PhotoImage(art.inventory(self.source,settings,96),master=self)
            self.preview.delete('all');self.preview.create_image(0,0,image=self.preview_photo,anchor='nw')
            self.inventory.delete('all');self.inventory.create_image(0,0,image=self.inventory_photo,anchor='nw')
            self.error.set('');self.draw_crop()
        except (ValueError,OSError) as exc:self.error.set(str(exc))
    def read(self):
        if not self.name.get().strip():raise ValueError('Вкажіть назву арту.')
        settings=self.settings();art.tile(self.source,settings,192)
        return self.name.get().strip(),next(k for k,v in art.GROUPS.items() if v==self.group.get()),self.source,settings
    def destroy(self):
        if self.pending:
            self.after_cancel(self.pending);self.pending=None
        super().destroy()


class ArtPanel(ttk.Frame):
    def __init__(self,parent,library,before,changed,on_save,events):
        super().__init__(parent,padding=10);self.library=library;self.before=before;self.changed=changed;self.on_save=on_save;self.events=events
        self.root=self.winfo_toplevel();self.current=None
        bar=ttk.Frame(self);bar.pack(fill='x',pady=(0,10))
        ttk.Label(bar,text='Арти',font=('Segoe UI',18,'bold')).pack(side='left')
        for label,command in [('Зберегти всі зміни',on_save),('Дублювати',self.duplicate),('Редагувати / замінити',self.edit),('Вибрати з імпортованого',self.import_existing),('Імпортувати файл…',self.import_file)]:
            ttk.Button(bar,text=label,command=command).pack(side='right',padx=4)
        panes=ttk.Panedwindow(self,orient='horizontal');panes.pack(fill='both',expand=True)
        left=ttk.Frame(panes,width=460);right=ttk.Frame(panes,padding=20);panes.add(left,weight=2);panes.add(right,weight=3)
        self.query=tk.StringVar();row(left,'Пошук назви / ID',self.query)
        self.group=tk.StringVar(value='Усі');row(left,'Категорія',self.group,['Усі']+list(art.GROUPS.values()))
        self.only_custom=tk.BooleanVar();ttk.Checkbutton(left,text='Лише імпортовані / замінені',variable=self.only_custom,command=self.rebuild).pack(anchor='w',pady=5)
        frame=ttk.Frame(left);frame.pack(fill='both',expand=True)
        self.list=ttk.Treeview(frame,columns=('group',),show='tree headings',selectmode='browse')
        self.list.heading('#0',text='Назва');self.list.heading('group',text='Категорія');self.list.column('#0',width=260);self.list.column('group',width=145)
        scroll=ttk.Scrollbar(frame,command=self.list.yview);scroll.pack(side='right',fill='y');self.list.configure(yscrollcommand=scroll.set);self.list.pack(fill='both',expand=True)
        self.list.bind('<<TreeviewSelect>>',self.select);self.list.bind('<Double-1>',lambda e:self.edit())
        self.title=tk.StringVar();ttk.Label(right,textvariable=self.title,font=('Segoe UI',15,'bold'),wraplength=650).pack(anchor='w')
        self.ident=tk.StringVar();ttk.Label(right,textvariable=self.ident).pack(anchor='w',pady=5)
        self.picture=tk.Canvas(right,width=192,height=192,bg='#495251',highlightthickness=0);self.picture.pack(anchor='w',pady=18)
        self.info=tk.StringVar();ttk.Label(right,textvariable=self.info,wraplength=610).pack(anchor='w',pady=8)
        ttk.Label(right,text='Де використовується',font=('Segoe UI',11,'bold')).pack(anchor='w',pady=(16,5))
        self.uses=tk.Text(right,height=8,wrap='word',state='disabled');self.uses.pack(fill='both',expand=True)
        ttk.Label(right,text='Новий арт одразу доступний у виборі зображень усіх розділів.\nЗаміна зберігає ID. Збережіть усі зміни й перезапустіть гру.',wraplength=620).pack(anchor='w',pady=14)
        self.status=tk.StringVar();ttk.Label(self,textvariable=self.status).pack(fill='x',pady=(8,0))
        self.query.trace_add('write',lambda *a:self.rebuild());self.group.trace_add('write',lambda *a:self.rebuild())
        self.rebuild()

    def rebuild(self):
        self.list.delete(*self.list.get_children());query=self.query.get().casefold();count=0
        for key,entry in sorted(self.library.entries.items(),key=lambda pair:pair[1].get('art_label',pair[0]).casefold()):
            label=entry.get('art_label',key);group=art.GROUPS[art.category(key,entry)]
            if query not in (key+' '+label).casefold() or (self.group.get()!='Усі' and self.group.get()!=group):continue
            if self.only_custom.get() and not entry.get('editor_source'):continue
            self.list.insert('','end',iid=key,text=label,values=[group]);count+=1
        self.status.set(f'{count} із {len(self.library.entries)} артів · Імпорт: PNG, JPG, WebP, BMP, статичний GIF')
        if self.current and self.list.exists(self.current):self.list.selection_set(self.current);self.show(self.current)
        elif self.list.get_children():self.list.selection_set(self.list.get_children()[0])
    def select(self,event=None):
        if self.list.selection():self.show(self.list.selection()[0])
    def show(self,key):
        self.current=key;entry=self.library.entries[key];self.title.set(entry.get('art_label',key));self.ident.set('ID: '+key)
        self.photo=sprites.photo(self.root,key,192);self.picture.delete('all')
        if self.photo:self.picture.create_image(0,0,image=self.photo,anchor='nw')
        self.info.set('Категорія: '+art.GROUPS[art.category(key,entry)]+('\nПочатковий файл збережений; обрізання та підгонку можна змінити.' if entry.get('editor_source') else '\nАрт із наявного атласу. Редагування створить окрему версію цього арту.'))
        uses=self.library.usage(key,self.events())
        self.uses.configure(state='normal');self.uses.delete('1.0','end');self.uses.insert('end','\n'.join(uses) if uses else 'Прямих посилань у каталогах подій і моделей не знайдено. Арт також може використовувати інтерфейс гри.');self.uses.configure(state='disabled')
    def apply(self,key,value):
        if value is None:return
        try:self.library.stage(key,*value)
        except (ValueError,OSError) as exc:messagebox.showerror('Арт не застосовано',str(exc),parent=self.root);return
        self.current=key;self.changed();self.query.set('');self.group.set('Усі');self.rebuild();self.list.see(key)
        self.status.set('Арт підготовлено · Натисніть «Зберегти всі зміни», щоб записати його в проєкт')
    def import_file(self):
        if not self.before():return
        path=filedialog.askopenfilename(parent=self.root,title='Імпортувати арт',filetypes=FILE_TYPES)
        if not path:return
        try:
            source=art.decode(path);value=ArtEditDialog(self.root,source,Path(path).stem).show()
            self.apply(self.library.next_id(),value)
        except (OSError,ValueError) as exc:messagebox.showerror('Не вдалося імпортувати',str(exc),parent=self.root)
    def edit(self):
        if not self.current or not self.before():return
        key=self.current;entry=self.library.entries[key]
        try:
            value=ArtEditDialog(self.root,self.library.source(key),entry.get('art_label',key),art.category(key,entry),self.library.settings(key)).show()
            self.apply(key,value)
        except (OSError,ValueError) as exc:messagebox.showerror('Не вдалося відкрити арт',str(exc),parent=self.root)
    def import_existing(self):
        if not self.before():return
        path=ImportedSourceDialog(self.root,self.library).show()
        if path is None:return
        try:
            name=next(r['name'] for r in self.library.imported_sources() if r['path']==path)
            value=ArtEditDialog(self.root,self.library.image_file(path),name).show()
            self.apply(self.library.next_id(),value)
        except (OSError,ValueError) as exc:messagebox.showerror('Не вдалося відкрити оригінал',str(exc),parent=self.root)
    def duplicate(self):
        if not self.current or not self.before():return
        entry=self.library.entries[self.current]
        try:
            self.apply(self.library.next_id(),(entry.get('art_label',self.current)+' (копія)',art.category(self.current,entry),self.library.source(self.current),self.library.settings(self.current)))
        except (OSError,ValueError) as exc:messagebox.showerror('Не вдалося скопіювати арт',str(exc),parent=self.root)
