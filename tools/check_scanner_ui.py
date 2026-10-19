"""Real Tk check of the elite hunt track scanner; never writes the user's save.

Optional argument: a folder for screenshots (needs ImageMagick `import`).
"""
import faulthandler
faulthandler.dump_traceback_later(90,exit=True)
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import ui.application as application
import ui.dialogs
from tkinter import messagebox
from tests.fixtures.quest_offer import offer_for
messagebox.showinfo=lambda *args,**kwargs: None
ui.dialogs.showinfo=lambda *args,**kwargs: None
SHOTS=Path(sys.argv[1]) if len(sys.argv)>1 else None
errors=[]


def shot(win,name):
    if not SHOTS:return
    SHOTS.mkdir(parents=True,exist_ok=True)
    win.update();subprocess.run(['import','-window',str(win.winfo_id()),str(SHOTS/name)],check=False,timeout=20)


def check(root,app):
    def failure(*args):
        errors.append(str(args));root.destroy()
    root.report_callback_exception=failure
    try:
        app.show_notice=lambda *args,**kwargs: None
        import game.model as model
        app.game=g=model.Game(4)
        offer=offer_for(g,'elite_hunt');assert g.accept_quest(offer['id'])
        q=g.quests[-1];g.x,g.y=q['pos'];start=q['pos'][:];app.refresh()
        app.act(g.search);root.update()
        win=app.dialog;view=win._scanner;s=q['scanner']
        assert g._scanner_request is None
        # Switched off: the lens jumps to the hand. Then scan the first print slowly.
        first=s['prints'][0]
        view.move(SimpleNamespace(x=first['x']-150,y=first['y']));view.tick();root.update()
        assert abs(s['lens'][0]-(first['x']-150))<1
        view.press(SimpleNamespace(x=first['x'],y=first['y']),True)
        for _ in range(4):view.last-=.1;view.tick()
        assert view.scanning and s['energy']<100 and s['lens'][0]<first['x']-100
        shot(win,'scanner_heavy.png')
        for _ in range(40):view.last-=.1;view.tick()
        assert s['read']>=1,s['read']
        shot(win,'scanner_found.png')
        view.press(SimpleNamespace(x=0,y=0),False)
        for p in s['prints']:
            if view.located:break
            view.move(SimpleNamespace(x=p['x'],y=p['y']));view.last-=.05;view.tick()
            view.press(SimpleNamespace(x=p['x'],y=p['y']),True);view.last-=.05;view.tick()
            view.press(SimpleNamespace(x=p['x'],y=p['y']),False)
        assert view.located and s['done'] and q['pos']!=start and q['track_index']==1
        root.update();shot(win,'scanner_located.png')
        win.close_dialog();root.update()
        assert view.closed and view.timer is None
    except Exception:
        import traceback;errors.append(traceback.format_exc())
    root.after(50,root.destroy)


application.launch(test_hook=check)
if errors:raise SystemExit('\n'.join(errors))
print('Scanner UI checked')
