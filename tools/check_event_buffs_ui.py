"""Check editable buff parameters and persist them in an isolated event catalog."""
import copy,sys,tempfile,tkinter as tk
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import event_catalog as ec
from event_editor import EffectDialog
root=tk.Tk();root.geometry('800x750')
for kind in ('wear_armor','radiation','radiation_heal','satiety_gain','satiety_loss','buff_regen','buff_satiety','buff_stealth'):
    win=EffectDialog(root,dict(kind=kind,amount=30,duration=12));root.update()
    assert str(win.duration_field.cget('state'))==('normal' if kind in ec.TIMED_EFFECTS else 'disabled')
    data=win.read();assert data['kind']==kind
    if kind in ec.TIMED_EFFECTS:assert data['duration']==12
    else:assert 'duration' not in data
    doc=copy.deepcopy(ec.DOCUMENT);doc['events']=doc['events'][:1]
    doc['events'][0]['choices'][0]['outcomes']=[dict(chance=1,effects=[data])]
    with tempfile.TemporaryDirectory() as folder:
        path=Path(folder)/'events.json';ec.save(doc,path);assert ec.load(path)==doc
    if kind=='buff_regen':
        win.duration.set('0')
        try:win.read();raise AssertionError('Zero duration accepted')
        except ValueError:pass
        win.duration.set('12')
        if len(sys.argv)>1:
            from PIL import ImageGrab
            win.lift();root.after(300,root.quit);root.mainloop();root.update_idletasks()
            ImageGrab.grab(bbox=(win.winfo_rootx(),win.winfo_rooty(),win.winfo_rootx()+win.winfo_width(),win.winfo_rooty()+win.winfo_height())).save(sys.argv[1])
    win.destroy()
root.destroy();print('PASS: eight effect forms, duration validation, save/reload without touching live events')
