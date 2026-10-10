"""In-window, themed replacements for native game message boxes."""
import tkinter as tk
from tkinter import ttk


def _show(title,message,choices,parent=None,art='journal',default=None,**kwargs):
    from visuals import PANEL,TEXT,GOLD
    import sprites
    owner=(parent or tk._default_root).winfo_toplevel()
    root=owner._root();app=getattr(root,'_afterdays_app',None)
    previous=getattr(app,'dialog',None);grab=owner.grab_current();focus=owner.focus_get()
    overlay=tk.Frame(owner,bg='#17221d');overlay.place(x=0,y=0,relwidth=1,relheight=1);overlay.lift()
    panel=tk.Frame(overlay,bg=PANEL,highlightthickness=1,highlightbackground=GOLD)
    panel.place(relx=.5,rely=.5,anchor='center',width=min(650,max(280,owner.winfo_width()-32)),height=min(580,max(250,owner.winfo_height()-32)))
    tk.Label(panel,text=title,bg=PANEL,fg=GOLD,font=('Segoe UI',16,'bold'),wraplength=500).pack(padx=16,pady=12)
    image=tk.Canvas(panel,width=96,height=96,bg=PANEL,highlightthickness=0);image.pack()
    sprites.draw(image,art,0,0,96)
    buttons=tk.Frame(panel,bg=PANEL);buttons.pack(side='bottom',padx=16,pady=16)
    body=tk.Frame(panel,bg=PANEL);body.pack(fill='both',expand=True,padx=20,pady=8)
    label=tk.Text(body,bg=PANEL,fg=TEXT,wrap='word',font=('Segoe UI',11),relief='flat',height=8)
    scrollbar=ttk.Scrollbar(body,command=label.yview);scrollbar.pack(side='right',fill='y')
    label.pack(fill='both',expand=True);label.configure(yscrollcommand=scrollbar.set)
    label.insert('1.0',message);label.configure(state='disabled')
    answer=[default]
    def close(value=default):
        answer[0]=value;overlay.destroy()
    for text,value in choices:ttk.Button(buttons,text=text,command=lambda v=value:close(v)).pack(side='left',padx=5)
    def escape(event):
        close();return 'break'
    def bind_escape(widget):
        widget.bind('<Escape>',escape)
        for child in widget.winfo_children():bind_escape(child)
    bind_escape(overlay)
    overlay.bind('<Return>',lambda e:close(choices[0][1]))
    if app:app.dialog=overlay;app.route.pause()
    overlay.grab_set();overlay.focus_set()
    try:owner.wait_window(overlay)
    finally:
        if app and app.dialog is overlay:app.dialog=previous if previous is not None and previous.winfo_exists() else None
        if grab is not None and grab.winfo_exists():grab.grab_set()
        if focus is not None and focus.winfo_exists():focus.focus_set()
    return answer[0]


def showinfo(title,message,**kwargs):return _show(title,message,[('Гаразд','ok')],default='ok',**kwargs)
def showerror(title,message,**kwargs):return _show(title,message,[('Гаразд','ok')],default='ok',**kwargs)
def askyesno(title,message,**kwargs):return _show(title,message,[('Так',True),('Ні',False)],default=False,**kwargs)
def askyesnocancel(title,message,**kwargs):return _show(title,message,[('Так',True),('Ні',False),('Скасувати',None)],**kwargs)
