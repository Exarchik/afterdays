"""Real Tk check of the junkyard pile minigame; never writes the user's save.

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
import junk_physics as pile
import game.items as items
messagebox.showinfo=lambda *args,**kwargs: None
ui.dialogs.showinfo=lambda *args,**kwargs: None
SHOTS=Path(sys.argv[1]) if len(sys.argv)>1 else None
errors=[]


def settle(root,seconds=.5):
    import time
    end=time.time()+seconds
    while time.time()<end:root.update();time.sleep(.01)


def shot(win,name):
    if not SHOTS:return
    SHOTS.mkdir(parents=True,exist_ok=True)
    win.update();subprocess.run(['import','-window',str(win.winfo_id()),str(SHOTS/name)],check=False,timeout=20)


def event(board,x,y):
    return SimpleNamespace(x=board.ox+x*board.scale,y=board.oy+y*board.scale)


def check(root,app):
    def failure(*args):
        errors.append(str(args));root.destroy()
    root.report_callback_exception=failure
    try:
        app.show_notice=lambda *args,**kwargs: None
        import game.model as model
        app.game=g=model.Game(4)
        offer=offer_for(g,'junkyard');assert g.accept_quest(offer['id'])
        q=g.quests[-1];g.x,g.y=q['pos'];g.bag.append(items.supply('food',2));app.refresh()
        assert g.search() and g._junkyard_request==q['id']
        g._junkyard_request=None
        import ui.junkyard as junkyard
        junkyard.show(app,q['id']);root.update()
        win=app.dialog;view=win._junkyard
        # Hover a blocked piece, then take free pieces from the top until satiety runs low.
        blocked=next(p for p in pile.live(q) if pile.blockers(q,p))
        x,y=blocked['x'],blocked['y'];view.motion(event(view,x,y));root.update()
        q['junk_settings']['settle_chance']=100
        removed=0;settled=None
        while g.hunger>8:
            left=g.junk_capacity(q)
            piece=max((p for p in pile.live(q) if not pile.blockers(q,p) and pile.MATERIALS[p['material']][1]<=left),key=lambda p:p['z'],default=None)
            if piece is None:break
            point=next((pt for pt in [(piece['x'],piece['y'])]+pile.corners(piece) if pile.piece_at(q,*pt) is piece),None)
            if point is None:break
            view.click(event(view,*point));removed+=1
            if g._junk_settled and not settled:
                settled=g._junk_settled;assert 'осіло' in view.message,view.message
                assert view.fresh and view.fresh[0]==settled['piece']
                settle(root,.3);shot(win,'junkyard_settled.png')
        assert removed>0 and g.hunger<20 and settled,(removed,g.hunger,settled)
        still=next((p for p in pile.live(q) if pile.blockers(q,p)),None)
        if still:view.motion(event(view,still['x'],still['y']))
        settle(root,2.5)
        shot(win,'junkyard_pile.png')
        before=g.hunger;food=next(i for i in g.junk_foods())
        view.eat(food['id']);assert g.hunger>before and 'ситість' in view.message
        shot(win,'junkyard_eaten.png')
        win.close_dialog()
    except Exception:
        import traceback;errors.append(traceback.format_exc())
    root.after(50,root.destroy)


application.launch(test_hook=check)
if errors:raise SystemExit('\n'.join(errors))
print('Junkyard UI checked')
