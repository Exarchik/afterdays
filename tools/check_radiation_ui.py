"""Real Tk check of the dosimeter minigame; never writes the user's save.

Optional argument: a folder for screenshots (needs ImageMagick `import`).
"""
import faulthandler
faulthandler.dump_traceback_later(60,exit=True)
import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import ui.application as application
from tkinter import messagebox
from tests.fixtures.quest_offer import offer_for
import world_hex
messagebox.showinfo=lambda *args,**kwargs: None
import ui.dialogs
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
        offer=offer_for(g,'radiation_source');assert g.accept_quest(offer['id'])
        q=g.radiation_quest(offer['id']);g.x,g.y=q['pos'];app.refresh()
        services=[entry[1] for entry in app.services.entries] if hasattr(app,'services') else []
        assert not services or 'Пошук джерела' in services,services
        import ui.radiation as radiation
        radiation.show(app,q['id']);board=app.dialog.dosimeter;root.update()
        ev=lambda x,y:type('E',(),dict(x=x,y=y))()
        mask=q['rad_sources'][1];dev=next(s for s in q['rad_sources'] if s['kind']=='device')
        # Sweep towards the strongest stray: the needle climbs and radiation accrues.
        for i in range(12):
            x,y=board.to_screen(mask['x']*i/11+.5*(11-i)/11,mask['y']*i/11+.5*(11-i)/11);board.motion(ev(x,y));root.after(60);root.update()
        for _ in range(10):root.after(45);root.update()
        assert board.shown>10,board.shown
        shot(app.dialog,'dosimeter_sweep.png')
        def hold(x,y):
            board.motion(ev(x,y));board.press(ev(x,y))
            end=__import__('time').monotonic()+radiation.DIG_SECONDS+.3
            while __import__('time').monotonic()<end:root.after(30);root.update()
            board.release(ev(x,y))
        hold(*board.to_screen(mask['x']+1.2,mask['y']))
        assert len(q['rad_holes'])==1,q['rad_holes']
        hold(*board.to_screen(mask['x'],mask['y']))
        assert mask['found'] and g.radiation_cleared(q)==1
        shot(app.dialog,'dosimeter_cleared.png')
        x,y=board.to_screen(dev['x'],dev['y']);board.motion(ev(x,y))
        board.start_dig(button=True)
        end=__import__('time').monotonic()+radiation.DIG_SECONDS+.3
        while __import__('time').monotonic()<end:root.after(30);root.update()
        assert g.quest_ready(q) and any(i.get('type_id')=='quest_radioactive_device' for i in g.bag)
        shot(app.dialog,'dosimeter_found.png')
        app.dialog.close_dialog()
        # The device goes back to the quest giver and disappears.
        g.x,g.y=g.cities[q['city']];app.refresh()
        assert g.turn_in(q['id']) and q['status']=='done'
        assert not any(i.get('type_id')=='quest_radioactive_device' for i in g.bag)
    except Exception as exc:
        import traceback;errors.append(traceback.format_exc())
    root.after(50,root.destroy)


application.launch(test_hook=check)
if errors:raise SystemExit('\n'.join(errors))
print('Dosimeter UI checked')
