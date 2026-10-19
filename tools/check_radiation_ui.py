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
        for cell in ((0,0),(5,5),(2,3)):
            x,y=board.center(*cell);board.click(type('E',(),dict(x=x,y=y))())
        assert len(q['rad_probes'])==3
        shot(app.dialog,'dosimeter_probes.png')
        x,y=board.center(*q['rad_source']);board.click(type('E',(),dict(x=x,y=y))())
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
