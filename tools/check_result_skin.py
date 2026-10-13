"""Check result layout at different sizes, overflow and empty results."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tkinter as tk
from ui.result_skin import ResultView
root=tk.Tk();root.geometry('760x650')
report=dict(title='Перемога',battle=True,art='event_theme:snare',rows=[
    dict(text='Нанесено шкоди: 101',effect_kind='damage_dealt',color='#9cdda8'),
    dict(text='Отримано шкоди: 35',effect_kind='damage',color='#e56860'),
    dict(text='Отримано досвіду: 20 XP',effect_kind='xp',color='#9cdda8')])
view=ResultView(root,report,lambda:None);view.pack(fill='both',expand=True);root.update()
assert not view.bar.winfo_ismapped()
from PIL import ImageGrab
root.lift();root.update()
ImageGrab.grab(bbox=(root.winfo_rootx(),root.winfo_rooty(),root.winfo_rootx()+root.winfo_width(),root.winfo_rooty()+root.winfo_height())).save('artifacts/battle-results-skinned.png')
report['title']='Перемога біля покинутого сховку на околиці старої промислової зони'
report['rows']*=12
for size in ('560x480','960x740'):
    root.geometry(size);view.schedule();root.update()
    assert view.bar.winfo_ismapped()
    view.scroll('moveto',1);root.update();assert view.offset==view.limit
    assert view.button.winfo_y()+view.button.winfo_height()<=view.winfo_height()
    assert view.button.winfo_y()>=view.content.winfo_y()+view.content.winfo_height()
report['rows']=[];view.schedule();root.update()
assert view.offset==0 and not view.bar.winfo_ismapped()
root.destroy();print('PASS: battle layout, long title, narrow/wide windows, overflow, empty result and fixed footer')
