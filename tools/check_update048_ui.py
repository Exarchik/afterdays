"""Exercise v0.48 UI without saving or modifying the user's game."""
import sys,traceback,tempfile
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import afterdays,world_hex
from tkinter import messagebox
messagebox.showinfo=lambda *a,**k:None
errors=[]
def check(root,app):
    try:
        root.report_callback_exception=lambda *args:errors.append(str(args))
        from test_scavenging import ScavengingTests
        g,q=ScavengingTests().quest('scout')
        app.game=g;app.refresh();g.pop_events();app.fx.active=[];app._notice_open=False
        if app.dialog:app.dialog.close_dialog()
        assert 'v0.48' in root.title()
        from action_ui048 import ActionButton
        buttons=[w for w in app.route_button.master.winfo_children() if isinstance(w,ActionButton)]
        assert len(buttons)==6
        assert all(w.art is None and w.cget('text') for w in buttons)
        app.route_button.show_tip();assert app.route_button.tip;app.route_button.hide_tip()
        start=(g.x,g.y);turn=g.turn
        nearby=next(p for p in world_hex.adjacent(start) if g.can_step(p[0]-g.x,p[1]-g.y))
        x,y=app.world_view.point(nearby);app.map_click(SimpleNamespace(x=x,y=y))
        assert app.route.path and not app.route.running and g.turn==turn
        assert app.route_button.cget('style')=='RouteReady048.TButton'
        app.route_button.invoke();assert app.route.running;app.route.pause()
        assert (g.x,g.y)==start
        q['pos']=list(max(g.player_reachable_world(start),key=lambda p:world_hex.distance(start,p)))
        app.quest_panel.selection=q['id'];app.quest_panel.refresh()
        app.quest_panel.navigate_button.invoke()
        assert app.route.path[-1]==tuple(q['pos']) and not app.route.running
        app.draw();assert app.canvas.find_withtag('quest_edge_arrow')
        root.attributes('-topmost',True);root.update_idletasks()
        from PIL import ImageGrab
        path=Path(tempfile.gettempdir())/'afterdays-v048.png'
        ImageGrab.grab(window=root.winfo_id()).save(path)
        print('Screenshot:',path,flush=True)
        print('PASS: icon placeholders, tooltip, map click waits, highlighted move, quest route, edge arrow',flush=True)
    except Exception:errors.append(traceback.format_exc())
    finally:root.destroy()
afterdays.launch(test_hook=check)
if errors:print('\n'.join(errors));raise SystemExit(1)
