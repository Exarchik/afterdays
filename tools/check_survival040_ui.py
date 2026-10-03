"""Exercise the real game HUD with radiation injury and both hunger states."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import afterdays
from terminal034 import snapshot
errors=[]


def hook(root,app):
    def fail(kind,error,trace):errors.append(error);root.destroy()
    root.report_callback_exception=fail
    def check():
        try:
            app.game=afterdays.Game(5);g=app.game
            g.survival.update(radiation=50,hunger=-10);g.hp=8
            app.refresh();root.update_idletasks()
            bar=app.status
            assert bar.find_withtag('radiation_fill')
            assert bar.itemcget(bar.find_withtag('hunger_fill')[0],'fill')=='#dc5b56'
            assert snapshot(g)['sickness'] and snapshot(g)['starving']
            for width in (1080,1440):
                root.geometry(f'{width}x820');root.update_idletasks();bar.paint()
                x1,y1,x2,y2=bar.coords(bar.find_withtag('radiation_fill')[0])
                assert x2>x1 and y2>y1
                assert any('Променева хвороба' in tip for box,tip,action in bar.regions)
            if len(sys.argv)>1:
                from PIL import ImageGrab
                root.after(400,root.quit);root.mainloop();root.update_idletasks()
                ImageGrab.grab(bbox=(root.winfo_rootx(),root.winfo_rooty(),root.winfo_rootx()+root.winfo_width(),root.winfo_rooty()+root.winfo_height())).save(sys.argv[1])
            g.survival.update(radiation=0,hunger=10);bar.refresh(g);root.update_idletasks()
            assert not bar.find_withtag('radiation_fill')
            assert bar.itemcget(bar.find_withtag('hunger_fill')[0],'fill')=='#4ba8df'
            assert 'v0.46' in root.title()
            print('Survival 0.40 UI passed: radiation HP segment, blue/red hunger, debuffs, resizing, version')
        except Exception as exc:errors.append(exc)
        finally:root.destroy()
    root.after(300,check)


afterdays.launch(test_hook=hook)
if errors:raise errors[0]
