"""Real Tk check of the torn-map minigame; never writes the user's save.

Optional argument: a folder for screenshots (needs ImageMagick `import`).
"""
import faulthandler
faulthandler.dump_traceback_later(180,exit=True)
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import ui.application as application
import ui.dialogs
from tkinter import messagebox
messagebox.showinfo=lambda *args,**kwargs: None
ui.dialogs.showinfo=lambda *args,**kwargs: None
from tests.fixtures.quest_offer import offer_for
import ui.restoration as restoration_ui
SHOTS=Path(sys.argv[1]) if len(sys.argv)>1 else None
errors=[]


def shot(win,name):
    if not SHOTS:return
    SHOTS.mkdir(parents=True,exist_ok=True)
    win.update();subprocess.run(['import','-window',str(win.winfo_id()),str(SHOTS/name)],check=False,timeout=20)


def settle(root,seconds=.5):
    end=time.time()+seconds
    while time.time()<end:root.update();time.sleep(.01)


def drag(view,i,x,y):
    """Drag piece i by mouse events so that its centre lands at table point (x,y)."""
    view.raise_group(i)  # pieces may lie on top of each other
    p=view.state["pieces"][i];sx,sy=view.point(p)
    view.press(SimpleNamespace(x=int(sx),y=int(sy)))
    assert view.drag and view.drag['i']==i,(i,view.drag)
    tx,ty=view.point((x,y))
    view.motion(SimpleNamespace(x=int(sx+(tx-sx)/2),y=int(sy+(ty-sy)/2)))
    view.release(SimpleNamespace(x=int(tx),y=int(ty)))


def check(root,app):
    def failure(*args):
        errors.append(str(args));root.destroy()
    root.report_callback_exception=failure
    try:
        app.show_notice=lambda *args,**kwargs: None
        import game.model as model
        app.game=g=model.Game(4)
        offer=offer_for(g,'torn_map');assert g.accept_quest(offer['id'])
        q=g.quests[-1];ident=q['id'];app.refresh()
        restoration_ui.puzzle(app,ident);settle(root,.8)
        win=app.dialog;view=win._torn_map;state=view.state
        assert view.S>0 and len(view.items)==len(state['pieces']),view.S
        shot(win,'map_start.png')
        # a click on a piece turns it
        r=state['pieces'][5][2];x,y=view.point(state['pieces'][5])
        view.press(SimpleNamespace(x=int(x),y=int(y)));view.release(SimpleNamespace(x=int(x),y=int(y)))
        assert state['pieces'][5][2]==(r+1)%4
        # straighten everything, then glue by real drags
        for i,p in enumerate(state['pieces']):
            while p[2]:view.turn(i)
        cols=state['cols']
        for i in range(len(state['pieces'])):
            drag(view,i,1+i%cols+.05,.8+i//cols-.04)
            if i==1:
                assert state['glued']==[[0,1]],state['glued']
                settle(root,.2);shot(win,'map_glued.png')
            if q['map_solved']:break
        settle(root,1.0)
        assert q['map_solved'] and q['pos']==q['stash_pos'],q.get('pos')
        assert view.c.find_withtag('stash') and view.c.find_withtag('cross')
        shot(win,'map_solved.png')
        # smaller window keeps the whole table visible
        win.geometry('700x560');settle(root,.6);assert view.S*6.4<=view.c.winfo_width()+1
        shot(win,'map_small.png')
        win.close_dialog();root.update()
    except Exception:
        import traceback;errors.append(traceback.format_exc())
    root.after(50,root.destroy)


application.launch(test_hook=check)
if errors:raise SystemExit('\n'.join(errors))
print('Torn map UI checked')
