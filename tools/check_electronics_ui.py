"""Real Tk check of the circuit-board repair minigame; never writes the user's save.

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
messagebox.showinfo=lambda *args,**kwargs: None
ui.dialogs.showinfo=lambda *args,**kwargs: None
from tests.fixtures.quest_offer import offer_for
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
        import ui.electronics as electronics
        app.game=g=model.Game(4)
        offer=offer_for(g,'electronics_repair');assert g.accept_quest(offer['id'])
        q=g.quests[-1];g.x,g.y=q['pos'];app.refresh()
        assert len(q['circuit_inventory'])==7,q['circuit_inventory']
        electronics.show(app,q['id']);root.update()
        win=app.dialog;board=win.circuit_board
        ev=lambda x,y:SimpleNamespace(x=x,y=y)
        def place(slot,turns):
            piece=q['circuit_target'][slot]
            cell=next(c for c in board.tray_cells() if c[0]==piece)
            board.press(ev(cell[1],cell[2]))
            x,y=electronics.CENTERS[slot];board.motion(ev(x,y))
            for _ in range(turns):board.rotate(None)
            return piece
        # Wrong rotation while hovering: some pads are red.
        piece=place(0,0)
        need=(q['circuit_angles'][0]-q['circuit_rotations'][str(piece)])%4
        board.rotate(None)
        if (q['circuit_rotations'][str(piece)]-q['circuit_angles'][0])%4==0:board.rotate(None)
        assert not g.circuit_fit(q,piece,0)['ok']
        shot(win,'electronics_hover_wrong.png')
        while (q['circuit_rotations'][str(piece)]-q['circuit_angles'][0])%4:board.rotate(None)
        assert g.circuit_fit(q,piece,0)['ok']
        shot(win,'electronics_hover_right.png')
        board.release(ev(*electronics.CENTERS[0]));assert q['circuit_slots'][0]==piece
        for slot in range(1,6):
            p=place(slot,0)
            turns=(q['circuit_angles'][slot]-q['circuit_rotations'][str(p)])%4
            if slot==4:turns=(turns+2)%4   # leave U5 turned by 180°
            for _ in range(turns):board.rotate(None)
            board.release(ev(*electronics.CENTERS[slot]))
        assert None not in q['circuit_slots']
        board.check();root.update()
        assert q['circuit_bad']==[4] and not q.get('circuit_checked'),q['circuit_bad']
        shot(win,'electronics_spark.png')
        x,y=electronics.CENTERS[4];board.mouse=(x,y)
        board.rotate(None);board.rotate(None);assert q['circuit_bad']==[]
        board.check();root.update()
        assert q['circuit_checked'] and g.quest_ready(q)
        root.after(200);root.update();shot(win,'electronics_done.png')
        win.close_dialog();root.update()
        assert board.flow_job is None
    except Exception:
        import traceback;errors.append(traceback.format_exc())
    root.after(50,root.destroy)


application.launch(test_hook=check)
if errors:raise SystemExit('\n'.join(errors))
print('Electronics UI checked')
