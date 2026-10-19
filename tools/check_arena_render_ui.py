"""Real Tk check of arena rendering speed and layering; never writes the user's save.

Prints per-frame times. Optional argument: a folder for a screenshot (needs ImageMagick `import`).
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
import ui.advanced as advanced_ui
SHOTS=Path(sys.argv[1]) if len(sys.argv)>1 else None
errors=[]


def check(root,app):
    def failure(*args):
        errors.append(str(args));root.destroy()
    root.report_callback_exception=failure
    try:
        app.show_notice=lambda *args,**kwargs: None
        import game.model as model
        app.game=g=model.Game(4);g.start_battle()
        root.geometry('1400x950');root.update();app.refresh();root.update()
        c=app.canvas
        app.draw();root.update()
        statics=c.find_withtag('arena_static');assert len(statics)==1,statics
        items=len(c.find_all());assert items<200,items
        static_photo=c._arena_static['photo']
        n=30;start=time.perf_counter()
        for _ in range(n):app.draw();root.update_idletasks()
        frame=(time.perf_counter()-start)/n*1000
        assert c.find_withtag('arena_static')==statics and c._arena_static['photo'] is static_photo
        assert abs(len(c.find_all())-items)<=2
        # Hovering only moves the marker: the floor image and units stay.
        enemy=g.battle['enemies'][0];x,y=advanced_ui.hexgrid.center(enemy['pos'],app.iso['u'],app.iso['ox'],app.iso['oy'])
        before=set(c.find_all())-set(c.find_withtag('hover'))-set(c.find_withtag('hit_chance'))
        start=time.perf_counter()
        for i in range(n):
            app.battle_hover=None;app.map_hover(SimpleNamespace(x=x,y=y+(i%2)*app.iso['u']*1.4))
            root.update_idletasks()
        hover=(time.perf_counter()-start)/n*1000
        assert before<=set(c.find_all()),'hover deleted arena items'
        app.map_hover(SimpleNamespace(x=x,y=y));root.update()
        assert c.find_withtag('hover')
        # The world map replaces the arena completely and the arena comes back intact.
        g.battle=None;app.draw();root.update();assert not c.find_withtag('arena_static')
        g.start_battle();app.draw();root.update();assert len(c.find_withtag('arena_static'))==1
        if SHOTS:
            SHOTS.mkdir(parents=True,exist_ok=True)
            subprocess.run(['import','-window',str(c.winfo_id()),str(SHOTS/'arena_render.png')],check=False,timeout=20)
        print(f'items {items}, frame {frame:.1f} ms, hover {hover:.2f} ms')
    except Exception:
        import traceback;errors.append(traceback.format_exc())
    root.after(50,root.destroy)


application.launch(test_hook=check)
if errors:raise SystemExit('\n'.join(errors))
print('Arena rendering checked')
