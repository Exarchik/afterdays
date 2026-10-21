"""Textured, responsive event/battle results with dynamic text and sprites."""
from ui.window_skin import BG, GOLD, TEXT, ASSET, panel_image
import tkinter as tk
from tkinter import ttk
import sprites
from event_results import groups




class ResultView(tk.Canvas):
    _owns_texture = True
    def __init__(self,parent,report,close):
        super().__init__(parent,bg=BG,highlightthickness=0)
        self.report=report;self.offset=0;self.limit=0;self.job=None;self.source=None;self.photos=[]
        try:
            from PIL import Image
            with Image.open(ASSET) as image:self.source=image.convert('RGB')
        except (ImportError,OSError):pass
        self.content=tk.Canvas(self,bg=BG,highlightthickness=0)
        self.bar=ttk.Scrollbar(self,orient='vertical',command=self.scroll)
        local=any(row.get('destination')=='loot' for row in report['rows'])
        self.button=tk.Button(self,text=('До сховку на локації' if local else 'Продовжити')+'   →',
            command=close,bg='#322e20',fg='#e4cf9e',activebackground='#51452c',activeforeground='#fff0cb',
            font=('Segoe UI',12),relief='flat',bd=0,highlightthickness=1,highlightbackground='#a38653',
            highlightcolor=GOLD,padx=20,pady=11,cursor='hand2',takefocus=True)
        self.bind('<Configure>',self.schedule)
        self.bind('<Destroy>',self.destroyed)
        for seq in ('<MouseWheel>','<Button-4>','<Button-5>'):parent.bind(seq,self.wheel)

    def destroyed(self,event):
        if event.widget is self and self.job:
            self.after_cancel(self.job);self.job=None

    def schedule(self,event=None):
        if self.job:self.after_cancel(self.job)
        self.job=self.after_idle(self.render)

    def scroll(self,*args):
        if args[0]=='moveto':self.offset=float(args[1])*self.total
        else:self.offset+=int(args[1])*(self.view_height*.85 if args[2]=='pages' else 32)
        self.offset=max(0,min(self.limit,self.offset));self.paint_rows()

    def wheel(self,event):
        direction=-1 if getattr(event,'num',None)==4 or getattr(event,'delta',0)>0 else 1
        self.scroll('scroll',direction,'units');return 'break'

    def divider(self,canvas,x,y,width):
        canvas.create_line(x,y,x+width,y,fill='#6d603f')
        for n in range(0,max(0,int(width)),19):
            canvas.create_line(x+n,y-1,x+min(width,n+7),y-1,fill='#9d8658')

    def render(self):
        self.job=None
        w=max(260,self.winfo_width());h=max(220,self.winfo_height())
        self.delete('all');self.photos=[];self.background=None
        if self.source is not None:
            from PIL import Image,ImageTk
            self.background=panel_image(w,h)
            photo=ImageTk.PhotoImage(self.background,master=self);self.photos.append(photo)
            self.create_image(0,0,image=photo,anchor='nw')
        else:
            self.create_rectangle(4,4,w-5,h-5,outline='#827049',width=3)
        pad=24 if w>=500 else 14
        art_size=144 if w<700 else 192
        if w<480:art_size=96
        x=pad+art_size+22;title_width=max(90,w-x-pad)
        heading=self.create_text(x,42,text=self.report['title'],anchor='nw',width=title_width,
                                 font=('Bahnschrift',25 if w>=600 else 19,'bold'),fill=GOLD)
        box=self.bbox(heading);line_y=box[3]+14
        self.divider(self,x,line_y,title_width)
        subtitle='Результати битви' if self.report.get('battle') else 'Результати події'
        sub=self.create_text(x,line_y+14,text=subtitle,anchor='nw',width=title_width,font=('Segoe UI',12),fill='#aaa896')
        bottom=self.bbox(sub)[3]
        if self.report.get('partial'):
            partial=self.create_text(x,bottom+9,text='Статистика від першої дії після оновлення гри.',anchor='nw',width=title_width,font=('Segoe UI',9),fill='#aaa896')
            bottom=self.bbox(partial)[3]
        if not sprites.draw(self,self.report.get('art'),pad,24,art_size):sprites.draw(self,'stash',pad,24,art_size)
        top=max(art_size+38,bottom+24)
        top=min(top,h-128)
        self.view_height=max(36,h-top-90);self.area_width=w-2*pad
        self.content.place(x=pad,y=top,width=self.area_width,height=self.view_height)
        self.area_x=pad;self.area_y=top
        self.button.place(relx=1,x=-pad,y=h-68,anchor='ne',height=46)
        self.create_rectangle(w-pad-self.button.winfo_reqwidth()-4,h-72,w-pad+4,h-18,outline='#8a7045',width=2)
        self.paint_rows()

    def paint_rows(self):
        c=self.content;c.delete('all')
        if not hasattr(self,'area_width'):return
        # The viewport texture remains stationary while the result rows scroll.
        if self.background is not None:
            from PIL import ImageTk
            self.content_photo=ImageTk.PhotoImage(self.background.crop((self.area_x,self.area_y,self.area_x+self.area_width,self.area_y+self.view_height)),master=self)
            c.create_image(0,0,image=self.content_photo,anchor='nw')
        width=self.area_width-18
        columns = max(1, min(3, int(width // 200)))
        cell = width / columns
        y=12-self.offset
        for title,rows in zip(('Стани','Предмети'),groups(self.report)):
            head=c.create_text(0,y,text=title,anchor='nw',font=('Bahnschrift',18,'bold'),fill=GOLD)
            box=c.bbox(head);self.divider(c,box[2]+16,y+16,max(0,width-box[2]-16))
            y+=48
            if not rows:
                c.create_text(4,y+10,text='Немає змін' if title=='Стани' else 'Немає предметів',anchor='nw',font=('Segoe UI',10),fill='#969b8c');y+=52
            for start in range(0,len(rows),columns):
                row_height=64
                for n,row in enumerate(rows[start:start+columns]):
                    x=n*cell
                    # Reuse the same icon resolution as existing results, translated into this row.
                    from ui.event import reward_icon
                    before=set(c.find_all());reward_icon(c,row)
                    for item in set(c.find_all())-before:c.move(item,x,y)
                    text=c.create_text(x+60,y+10,text=row['text'],anchor='nw',width=max(40,cell-74),
                                       font=('Segoe UI',10),fill=row.get('color',TEXT))
                    row_height=max(row_height,c.bbox(text)[3]-y+16)
                y+=row_height
            y+=22
        self.total=y+self.offset
        self.limit=max(0,self.total-self.view_height)
        if self.offset>self.limit:
            self.offset=self.limit;self.paint_rows();return
        if self.limit:
            self.bar.place(x=self.area_x+self.area_width-12,y=self.area_y,width=12,height=self.view_height)
            self.bar.set(self.offset/self.total,min(1,(self.offset+self.view_height)/self.total))
        else:self.bar.place_forget()
