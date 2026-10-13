"""Exercise shared popup borders, dynamic content and normal Tk geometry managers."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tkinter as tk
from tkinter import ttk
from ui.window_skin import apply, clear_content, panel_image
root=tk.Tk();root.withdraw()
errors=[]
root.report_callback_exception=lambda *args: errors.append(args)
win=tk.Toplevel(root);apply(win)
for size in ('420x240','760x650','1000x730'):
    win.geometry(size)
    body=tk.Frame(win,bg='#202b27');body.pack(fill='both',expand=True)
    tk.Label(body,text='Сховок на локації',bg='#202b27').pack()
    button=ttk.Button(body,text='Продовжити');button.pack(side='bottom')
    root.update()
    assert button.cget('style')=='Survival.TButton'
    assert body.winfo_x()>=14 and body.winfo_y()>=14
    assert body.winfo_width()<=win.winfo_width()-28
    assert win._game_skin.size==(win.winfo_width(),win.winfo_height())
    clear_content(win);root.update()
    assert win._game_skin.canvas.winfo_exists()
# Corner pixels stay identical at different dimensions.
a=panel_image(420,240);b=panel_image(1000,730)
if a is not None:
    assert a.crop((0,0,24,24)).tobytes()==b.crop((0,0,24,24)).tobytes()
# Grid content also retains the border.
panel=tk.Frame(win,bg='#202b27');panel.grid(sticky='nsew')
win.rowconfigure(0,weight=1);win.columnconfigure(0,weight=1)
root.update();assert panel.winfo_x()>=14
if '--screenshot' in sys.argv:
    panel.destroy()
    win.geometry('620x400');win.title('Сховок на локації')
    tk.Label(win,text='Сховок на локації',bg='#202b27',fg='#d4b477',font=('Segoe UI',22,'bold')).pack(pady=24)
    tk.Label(win,text='Предмети та спорядження',bg='#202b27',fg='#d9d3bf',font=('Segoe UI',12)).pack()
    ttk.Button(win,text='Продовжити →').pack(side='bottom',anchor='e',padx=16,pady=18)
    win.lift();win.attributes('-topmost',True);root.update()
    def capture():
        from PIL import ImageGrab
        ImageGrab.grab(bbox=(win.winfo_rootx(),win.winfo_rooty(),win.winfo_rootx()+win.winfo_width(),win.winfo_rooty()+win.winfo_height())).save('artifacts/window-skin.png')
        root.quit()
    root.after(800,capture);root.mainloop()
win.destroy();root.update();root.destroy()
assert not errors, errors
print('PASS: shared skin, fixed corners, compact/large sizes, pack/grid, content replacement and teardown')
