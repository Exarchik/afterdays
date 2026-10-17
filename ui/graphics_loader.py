"""Warm game graphics on one Tk root before exposing interactive gameplay."""
from pathlib import Path
from queue import Queue,Empty,Full
from threading import Thread,Event
from time import perf_counter
from types import SimpleNamespace
import tkinter as tk
from tkinter import ttk
import sprites


def sheet_jobs():
    jobs={}
    for entry in sprites.MANIFEST.values():
        for group,field,default,sizes in (
            ('sprite','sheet','atlas',sprites.SIZES),
            ('inventory','inventory_sheet','inventory',(48,56,64,80,96,128))):
            sheet=entry.get(field,default)
            for size in sizes:jobs[group,sheet,size]=sprites.ROOT/f'{sheet}_{size}.png'
    return list(jobs.items())


def decode_sheets(jobs,queue,stop):
    """Only file/Pillow operations run here; Tk always stays on the main thread."""
    from PIL import Image
    for identity,path in jobs:
        if stop.is_set():return
        image=None;error=None;recovered=None
        try:
            with Image.open(path) as source:image=source.convert('RGBA')
        except (OSError,ValueError) as exc:
            error=str(exc)
            group,sheet,size=identity
            sizes=(48,56,64,80,96,128) if group=='inventory' else sprites.SIZES
            for other in sorted((s for s in sizes if s!=size),key=lambda s:abs(s-size)):
                candidate=sprites.ROOT/f'{sheet}_{other}.png'
                try:
                    with Image.open(candidate) as source:
                        height=source.height if group=='inventory' else round(source.height*size/other)
                        image=source.convert('RGBA').resize((round(source.width*size/other),height),Image.Resampling.LANCZOS)
                    recovered=(str(path),str(candidate));error=None;break
                except (OSError,ValueError):pass
        while not stop.is_set():
            try:queue.put((identity,image,error,recovered),timeout=.1);break
            except Full:pass


class GraphicsLoader(tk.Frame):
    def __init__(self,root,create_app,on_ready=None):
        import PIL.Image  # Fail visibly on startup if Pillow is unavailable.
        super().__init__(root,bg='#141c1a')
        self.root=root;self.create_app=create_app;self.on_ready=on_ready
        self.stop=Event();self.queue=Queue(maxsize=2);self.errors=[];self.recovered=[];self.started=perf_counter()
        self.place(x=0,y=0,relwidth=1,relheight=1)
        body=tk.Frame(self,bg='#141c1a');body.place(relx=.5,rely=.5,anchor='center')
        tk.Label(body,text='A F T E R D A Y S',font=('Segoe UI',24,'bold'),fg='#d7b77a',bg='#141c1a').pack(pady=18)
        self.label=tk.Label(body,text='Передзавантаження графіки…',font=('Segoe UI',12),fg='#e4e8d9',bg='#141c1a');self.label.pack(pady=10)
        self.bar=ttk.Progressbar(body,length=480,maximum=100);self.bar.pack(pady=10)
        tk.Label(body,text='Зображення залишатимуться в пам’яті до закриття гри.',fg='#a4b2a4',bg='#141c1a').pack(pady=10)
        root._sprite_cache={};root._sprite_sheets={};root._sprite_tiles={}
        root._sprite_sources={};root._inventory_sources={}
        root._inventory_images={};root._inventory_sheets={}
        self.jobs=sheet_jobs();self.received=0
        self.bind('<Destroy>',lambda event:self.stop.set() if event.widget is self else None)
        self.after(30,self.start)

    def start(self):
        Thread(target=decode_sheets,args=(self.jobs,self.queue,self.stop),daemon=True,name='graphics-loader').start()
        self.poll()

    def poll(self):
        deadline=perf_counter()+.012
        while self.received<len(self.jobs) and perf_counter()<deadline:
            try:identity,image,error,recovered=self.queue.get_nowait()
            except Empty:break
            group,sheet,size=identity
            target=self.root._sprite_sources if group=='sprite' else self.root._inventory_sources
            target[sheet,size]=image
            if error:self.errors.append((str(sprites.ROOT/f'{sheet}_{size}.png'),error))
            if recovered:self.recovered.append(recovered)
            self.received+=1
        self.bar['value']=60*self.received/max(1,len(self.jobs))
        self.label.config(text=f'Завантаження атласів: {self.received} / {len(self.jobs)}')
        if self.received<len(self.jobs):self.after(10,self.poll)
        else:
            self.tasks=iter(self.sprite_tasks());self.completed=0
            self.total=len(sprites.MANIFEST)*(len(sprites.SIZES)+6)
            self.after(1,self.warm)

    def sprite_tasks(self):
        for key in sprites.MANIFEST:
            for size in sprites.SIZES:
                yield lambda key=key,size=size:sprites.photo(self.root,key,size)
            for width in (48,56,64,80,96,128):
                yield lambda key=key,width=width:sprites.inventory_photo(self.root,{'kind':'weapon','sprite_id':key},width)

    def warm(self):
        deadline=perf_counter()+.012
        while perf_counter()<deadline:
            task=next(self.tasks,None)
            if task is None:
                self.label.config(text='Підготовка мапи…');self.bar['value']=95
                self.after(10,self.prepare_map);return
            task();self.completed+=1
        self.bar['value']=60+35*self.completed/max(1,self.total)
        self.label.config(text=f'Підготовка зображень: {self.completed} / {self.total}')
        self.after(1,self.warm)

    def prepare_map(self):
        from ui.electronics import prepare_art
        prepare_art(self.root)
        self.app=self.create_app(self.root)
        self.lift();self.grab_set();self.focus_set()
        self.root.update_idletasks()
        import world_map
        from ui.location_panel import CITY_ART_SIZE
        g=self.app.game
        radius=world_map.layout(self.app.canvas.winfo_width(),self.app.canvas.winfo_height(),len(g.world[0]),len(g.world),(g.x,g.y)).radius
        self.hex_tasks=iter((kind,x,r) for r in (radius,CITY_ART_SIZE/2) for kind in world_map.COLORS for x in range(8))
        self.after(1,self.warm_map)

    def warm_map(self):
        import world_hex_art
        deadline=perf_counter()+.012
        while perf_counter()<deadline:
            job=next(self.hex_tasks,None)
            if job is None:
                self.root._graphics_preload_report={'seconds':perf_counter()-self.started,'errors':self.errors,'recovered':self.recovered,'sheets':len(self.jobs),'images':self.completed}
                self.grab_release();self.destroy()
                if self.on_ready:self.on_ready(self.root,self.app)
                return
            kind,x,radius=job
            world_hex_art.photo(self.root,SimpleNamespace(world=[[kind]*8]),x,0,radius)
        self.after(1,self.warm_map)
