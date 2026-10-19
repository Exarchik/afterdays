"""Real Tk check of the generator load-balancing minigame; never writes the user's save.

Optional argument: a folder for screenshots (needs ImageMagick `import`).
"""
import faulthandler
faulthandler.dump_traceback_later(90,exit=True)
import subprocess
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import ui.application as application
import ui.dialogs
from tkinter import messagebox
messagebox.showinfo=lambda *args,**kwargs: None
ui.dialogs.showinfo=lambda *args,**kwargs: None
from tests.fixtures.quest_offer import offer_for
import game.items as items
from game.systems import generator_balance as balance
SHOTS=Path(sys.argv[1]) if len(sys.argv)>1 else None
errors=[]


def shot(win,name):
    if not SHOTS:return
    SHOTS.mkdir(parents=True,exist_ok=True)
    win.update();subprocess.run(['import','-window',str(win.winfo_id()),str(SHOTS/name)],check=False,timeout=20)


def settle(root,seconds=.6):
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
        offer=offer_for(g,'generator');assert g.accept_quest(offer['id'])
        q=g.quests[-1];g.x,g.y=q['pos'];items.add_to(g.bag,items.parts(20));items.add_to(g.bag,items.fragments(20));app.refresh()
        app.act(g.search);root.update()
        win=app.dialog;panel=win._generator
        weights=q['generator_weights'];lo,hi=q['generator_zone']
        # Overload: heaviest switches first.
        total=0
        for i in sorted(range(len(weights)),key=lambda i:-weights[i]):
            panel.toggle(i);total+=weights[i]
            if total>balance.RED:break
        assert panel.spark is not None and not any(q['generator_on'])
        settle(root,.2);shot(win,'generator_overload.png');settle(root,.8)
        assert panel.spark is None
        mask=next(m for m,s in balance.subset_sums(weights) if lo<=s<=hi)
        for i in sorted((i for i in range(len(weights)) if mask>>i&1),key=lambda i:weights[i]):panel.toggle(i)
        settle(root);assert balance.in_zone(q) and str(panel.finish['state'])=='normal'
        shot(win,'generator_zone.png')
        panel.confirm();assert q['progress']==1 and g.quest_ready(q)
        win.close_dialog();root.update();assert panel.timer is None
    except Exception:
        import traceback;errors.append(traceback.format_exc())
    root.after(50,root.destroy)


application.launch(test_hook=check)
if errors:raise SystemExit('\n'.join(errors))
print('Generator UI checked')
