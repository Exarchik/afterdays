"""Regression checks for textured labels, content canvases and read-only text."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tkinter as tk
from tkinter import ttk
from ui.window_skin import apply,clear_content
root=tk.Tk();root.withdraw();win=tk.Toplevel(root);win.geometry('620x460');apply(win)
errors=[]
root.report_callback_exception=lambda *args:errors.append(args)
frame=tk.Frame(win,bg='#202b27');frame.pack(fill='both',expand=True,padx=12,pady=12)
variable=tk.StringVar(value='Сховок на локації')
label=tk.Label(frame,textvariable=variable,bg='#202b27',fg='#d4b477',font=('Segoe UI',20,'bold'));label.pack(pady=12)
canvas=tk.Canvas(frame,height=60,bg='#202b27',highlightthickness=0);canvas.pack(fill='x')
canvas.create_text(20,20,text='Предмети та спорядження',fill='#d9d3bf',anchor='nw')
body=tk.Text(frame,height=5,bg='#202b27',fg='#d9d3bf',wrap='word',font=('Segoe UI',11))
body.pack(fill='both',expand=True)
body.insert('1.0','Знайдено сховок.\nДосвід: +20 XP\nЗапчастини: +8\n')
body.tag_configure('good',foreground='#91e6ab');body.tag_add('good','2.0','4.0');body.configure(state='disabled')
ttk.Button(frame,text='Продовжити →').pack(side='bottom',anchor='e',pady=12)
root.update()
skin=win._game_skin
assert label in skin.surfaces and body in skin.surfaces
surface=skin.surfaces[label]
assert surface.canvas.itemcget(surface.canvas.find_withtag('_skin_label')[0],'text')==variable.get()
variable.set('Перемога');root.update()
assert surface.canvas.itemcget(surface.canvas.find_withtag('_skin_label')[0],'text')=='Перемога'
variable.set('Сховок на локації');root.update()
canvas.delete('all');canvas.create_text(20,20,text='Предмети та спорядження',fill='#d9d3bf',anchor='nw');root.update()
assert canvas.find_withtag('_skin_background')
assert canvas.bbox('all')[2]<400
# Native disabled text remains scrollable and accepts content refresh.
body.configure(state='normal');body.insert('end','Додатковий рядок\n'*30);body.configure(state='disabled');root.update()
body.yview_moveto(1);root.update()
assert body.yview()[0]>0
assert skin.surfaces[body].canvas.find_withtag('_skin_text')
body.configure(state='normal');body.delete('4.0','end');body.configure(state='disabled');body.yview_moveto(0);root.update()
if '--screenshot' in sys.argv:
    win.lift();win.attributes('-topmost',True);root.update()
    def capture():
        from PIL import ImageGrab
        ImageGrab.grab(bbox=(win.winfo_rootx(),win.winfo_rooty(),win.winfo_rootx()+win.winfo_width(),win.winfo_rooty()+win.winfo_height())).save('artifacts/textured-popup.png')
        root.quit()
    root.after(600,capture);root.mainloop()
clear_content(win);root.update();assert variable.get()=='Сховок на локації'
win.destroy();root.destroy();assert not errors,errors
print('PASS: texture surfaces, live labels, textvariable lifetime, canvas repaint/bbox, read-only text scrolling and replacement')
