"""A compact, modal conversation inside the world-map canvas."""
import tkinter as tk
import sprites
from dialogue_text import Presentation, hero, speak_reply

BG='#17231e'
TEXT='#e6e9de'
MUTED='#a8bcad'


class DialogueOverlay(tk.Frame):
    def __init__(self,panel,session):
        self.panel=panel;self.app=panel.app;self.session=session
        # A sibling placed relative to the canvas stays above its native repaint surface.
        super().__init__(self.app.canvas.master,bg=BG,highlightthickness=1,highlightbackground='#536658')
        self.app.route.pause();self.app.dialog=self
        self.place(in_=self.app.canvas,relx=.5,rely=1,anchor='s',y=-12)
        self.portrait=tk.Label(self,bg=BG)
        self.viewport=tk.Canvas(self,bg=BG,highlightthickness=0)
        self.body=tk.Frame(self.viewport,bg=BG)
        self.body_id=self.viewport.create_window(0,0,window=self.body,anchor='nw')
        self.body.bind('<Configure>',lambda e:self.viewport.configure(scrollregion=self.viewport.bbox('all')))
        self.widgets=[];self.layout_job=None;self.error=''
        self.presentation=Presentation(self)
        self.resize_binding=self.app.canvas.bind('<Configure>',self.schedule_layout,add='+')
        self.bind('<Escape>',lambda e:self.close_dialog())
        self.bind('<MouseWheel>',self.scroll)
        self.close_dialog=self.close
        self.grab_set();self.focus_set();self.render()

    def scroll(self,event):
        self.viewport.yview_scroll(-1 if event.delta>0 else 1,'units');return 'break'

    def schedule_layout(self,event=None):
        if self.layout_job:self.after_cancel(self.layout_job)
        self.layout_job=self.after_idle(self.layout)

    def layout(self):
        self.layout_job=None
        if not self.winfo_exists():return
        width=max(200,self.app.canvas.winfo_width()-24)
        text_width=max(80,width-144)
        for widget in self.widgets:widget.configure(wraplength=text_width-12)
        self.viewport.itemconfigure(self.body_id,width=text_width)
        self.body.update_idletasks()
        height=min(max(128,self.body.winfo_reqheight()+24),max(100,int(self.app.canvas.winfo_height()*.55)))
        self.place_configure(width=width,height=height)
        self.lift()

    def render(self,spoken=None):
        self.presentation.cancel()
        if self.session.block is None:
            self.close();self.panel.refresh();self.app.refresh();return
        for widget in self.body.winfo_children():widget.destroy()
        self.widgets=[];actor=hero(self.session) if spoken else self.session.actor()
        self.photo=sprites.photo(self,actor['art'],96)
        self.portrait.configure(image=self.photo or '')
        self.portrait.pack_forget();self.viewport.pack_forget()
        side='left' if spoken or self.session.block['actor']=='player' else 'right'
        self.portrait.pack(side=side,anchor='n',padx=12,pady=16)
        self.viewport.pack(side='left',fill='both',expand=True,padx=12,pady=12)
        def label(text,color=TEXT,font=('Segoe UI',11),pady=0):
            widget=tk.Label(self.body,text=text,bg=BG,fg=color,anchor='w',justify='left',font=font)
            widget.pack(fill='x',pady=pady);self.widgets.append(widget)
            return widget
        label(actor['name'],MUTED,('Segoe UI',9,'bold'))
        phrase=label('',pady=(4,10))
        hint=label('',MUTED)
        replies=[];controls=[]
        for reply in ([] if spoken else self.session.replies()):
            button=self.button('',lambda key=reply['id']:self.choose(key))
            replies.append((button,reply['text']));controls.append(button)
        if not spoken and not self.session.block.get('replies'):
            controls.append(self.button('Далі' if self.session.block.get('next') else 'Завершити',self.choose))
        elif not spoken and not self.session.replies():
            label('Немає доступних відповідей.',MUTED)
            self.button('Закрити',self.close)
        if self.error:label(self.error,'#e9a28c',pady=4)
        # Bind wheel/escape on children too, without changing game-wide key bindings.
        for widget in [self.viewport,self.body,self.portrait]+list(self.body.winfo_children()):
            widget.bind('<MouseWheel>',self.scroll)
            widget.bind('<Escape>',lambda e:self.close())
        show_hint=lambda waiting: hint.configure(text='Натисніть будь-яку клавішу або кнопку миші…' if waiting else '')
        if spoken:speak_reply(self.presentation,spoken['text'],phrase,show_hint,lambda:self.finish_choice(spoken['id']),self.schedule_layout)
        else:self.presentation.show(self.session.block['text'],phrase,replies,controls,show_hint,self.schedule_layout)
        self.presentation.bind_inputs(self)
        self.focus_set()
        self.viewport.yview_moveto(0);self.schedule_layout()

    def button(self,text,command):
        widget=tk.Button(self.body,text=text,command=command,anchor='w',justify='left',
            bg=BG,fg='#d3dfbb',activebackground='#2b3d31',activeforeground='#ffffff',
            relief='flat',borderwidth=0,highlightthickness=0,padx=6,pady=4,font=('Segoe UI',10))
        widget.pack(fill='x',pady=1);self.widgets.append(widget)
        return widget

    def choose(self,key=None):
        if self.presentation.player.active:return
        if key is not None:
            reply=next((r for r in self.session.replies() if r['id']==key),None)
            if reply:self.render(reply)
            return
        self.finish_choice()
    def finish_choice(self,key=None):
        try:self.session.choose(key);self.error=''
        except ValueError as exc:self.error=str(exc)
        self.render();self.app.refresh()

    def close(self):
        self.presentation.cancel()
        if not self.winfo_exists():return
        if self.layout_job:self.after_cancel(self.layout_job);self.layout_job=None
        self.app.canvas.unbind('<Configure>',self.resize_binding)
        if self.grab_current() is self:self.grab_release()
        if self.app.dialog is self:self.app.dialog=None
        self.destroy();self.app.canvas.focus_set()


def show(panel,ident):
    session=panel.app.game.story_session(ident)
    # Close the story journal (and its modal parent) before placing the conversation on the map.
    while panel.app.dialog:
        dialog=panel.app.dialog
        dialog.close_dialog()
    return DialogueOverlay(panel,session)
