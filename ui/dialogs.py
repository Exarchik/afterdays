"""Compact themed modal message windows."""
import tkinter as tk
from tkinter import ttk


def _show(title,message,choices,parent=None,art='journal',default=None,**kwargs):
    from visuals import PANEL,TEXT,GOLD
    import sprites
    owner=(parent or tk._default_root).winfo_toplevel()
    root=owner._root();app=getattr(root,'_afterdays_app',None)
    previous=getattr(app,'dialog',None);grab=owner.grab_current();focus=owner.focus_get()
    active=grab or previous
    if active is not None and active.winfo_exists():owner=active.winfo_toplevel()
    overlay=tk.Toplevel(owner);overlay.withdraw();overlay.title(title)
    overlay.configure(bg=PANEL);overlay.transient(owner);overlay.resizable(False,False)
    panel=tk.Frame(overlay,bg=PANEL,highlightthickness=1,highlightbackground=GOLD)
    panel.pack(fill='both',expand=True)
    width=min(540,owner.winfo_screenwidth()-40)
    tk.Label(panel,text=title,bg=PANEL,fg=GOLD,font=('Segoe UI',16,'bold'),wraplength=width-40).pack(padx=16,pady=12)
    image=tk.Canvas(panel,width=96,height=96,bg=PANEL,highlightthickness=0);image.pack()
    sprites.draw(image,art,0,0,96)
    buttons=tk.Frame(panel,bg=PANEL);buttons.pack(side='bottom',padx=16,pady=16)
    body=tk.Frame(panel,bg=PANEL);body.pack(fill='both',expand=True,padx=20,pady=8)
    label=tk.Text(body,bg=PANEL,fg=TEXT,wrap='word',font=('Segoe UI',11),relief='flat',width=1,height=4)
    scrollbar=ttk.Scrollbar(body,command=label.yview);scrollbar.pack(side='right',fill='y')
    label.pack(fill='both',expand=True)
    from ui.scrolling import auto_scrollbar
    auto_scrollbar(label,scrollbar)
    label.insert('1.0',message);label.configure(state='disabled')
    answer=[default]
    def close(value=default):
        answer[0]=value;overlay.destroy()
    for text,value in choices:ttk.Button(buttons,text=text,command=lambda v=value:close(v)).pack(side='left',padx=5)
    overlay.protocol('WM_DELETE_WINDOW',close)
    overlay.bind('<Escape>',lambda e:close())
    overlay.bind('<Return>',lambda e:close(choices[0][1]))
    overlay.update_idletasks()
    height=min(overlay.winfo_reqheight(),owner.winfo_screenheight()-80)
    x=max(0,min(owner.winfo_rootx()+(owner.winfo_width()-width)//2,owner.winfo_screenwidth()-width))
    y=max(0,min(owner.winfo_rooty()+(owner.winfo_height()-height)//2,owner.winfo_screenheight()-height-40))
    overlay.geometry(f'{width}x{height}+{x}+{y}')
    if app:app.dialog=overlay;app.route.pause()
    overlay.deiconify();overlay.lift()
    try:
        overlay.wait_visibility();overlay.grab_set();overlay.focus_set()
        owner.wait_window(overlay)
    finally:
        if app and app.dialog is overlay:app.dialog=previous if previous is not None and previous.winfo_exists() else None
        if grab is not None and grab.winfo_exists():grab.grab_set()
        if focus is not None and focus.winfo_exists():focus.focus_set()
    return answer[0]


def showinfo(title,message,**kwargs):return _show(title,message,[('Гаразд','ok')],default='ok',**kwargs)
def showerror(title,message,**kwargs):return _show(title,message,[('Гаразд','ok')],default='ok',**kwargs)
def askyesno(title,message,**kwargs):return _show(title,message,[('Так',True),('Ні',False)],default=False,**kwargs)
def askyesnocancel(title,message,**kwargs):return _show(title,message,[('Так',True),('Ні',False),('Скасувати',None)],**kwargs)
