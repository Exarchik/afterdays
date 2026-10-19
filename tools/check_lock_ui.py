"""Real Tk check of the disc lock minigame (quest cache and road cache); never writes the user's save.

Optional argument: a folder for screenshots (needs ImageMagick `import`).
"""
import faulthandler
faulthandler.dump_traceback_later(120,exit=True)
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
from tests.fixtures.disc_lock import moves
import game.items as items
import ui.lock as lock_ui
SHOTS=Path(sys.argv[1]) if len(sys.argv)>1 else None
errors=[]


def shot(win,name):
    if not SHOTS:return
    SHOTS.mkdir(parents=True,exist_ok=True)
    win.update();subprocess.run(['import','-window',str(win.winfo_id()),str(SHOTS/name)],check=False,timeout=20)


def settle(root,seconds=.5):
    end=time.time()+seconds
    while time.time()<end:root.update();time.sleep(.01)


def check(root,app):
    def failure(*args):
        errors.append(str(args));root.destroy()
    root.report_callback_exception=failure
    try:
        app.show_notice=lambda *args,**kwargs: None
        import game.model as model
        app.game=g=model.Game(4)
        offer=offer_for(g,'cache');assert g.accept_quest(offer['id'])
        q=g.quests[-1];g.x,g.y=q['cache_pos'];items.add_to(g.bag,items.parts(6));app.refresh()
        app.act(g.search);root.update();settle(root,.2)
        win=app.dialog;view=win._disc_lock;canvas=view.canvas
        state=q['lock_disc'];parts=g.count('parts')
        # premature open breaks a pick
        view.attempt();settle(root,.3)
        assert g.count('parts')==parts-1,(parts,g.count('parts'))
        shot(win,'lock_fail.png')
        # click on the outer ring's right half turns it clockwise
        n=len(state['pos']);r=view.ring_radius(n-1)
        before=state['pos'][:]
        view.click(SimpleNamespace(x=lock_ui.CX+r,y=lock_ui.CY))
        settle(root,.3);assert state['pos']!=before and state['turned']==1
        view.click(SimpleNamespace(x=lock_ui.CX-r,y=lock_ui.CY));settle(root,.2)
        assert state['pos']==before
        shot(win,'lock_turn.png')
        for ring,direction in moves(state):
            g.lock_turn(q['id'],ring,direction)
        view.animate();settle(root,.6)
        shot(win,'lock_aligned.png')
        view.attempt();settle(root,.3);shot(win,'lock_open.png');settle(root,.8)
        assert q['lock_open'] and q['progress']==1
        if app.dialog and app.dialog.winfo_exists():app.dialog.close_dialog()
        root.update()
        # road cache from an event
        import event_catalog
        spec=next(s for s in event_catalog.BY_ID.values() if s['id'].startswith('locked_') and 'cache' in s)
        g.x,g.y=g.cities[0][0]+1,g.cities[0][1]
        g.begin_event_cache(spec);ident=g._lock_request;g._lock_request=None
        lock_ui.show(app,ident);root.update();settle(root,.3)
        cache=g.lock_context(ident);assert cache['lock_disc']['version']==1
        shot(app.dialog,'lock_road.png')
        for ring,direction in moves(cache['lock_disc']):g.lock_turn(ident,ring,direction)
        app.dialog._disc_lock.attempt();settle(root,1.0)
        assert cache['opened']
    except Exception:
        import traceback;errors.append(traceback.format_exc())
    root.after(50,root.destroy)


application.launch(test_hook=check)
if errors:raise SystemExit('\n'.join(errors))
print('Disc lock UI checked')
