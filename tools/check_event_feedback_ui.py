"""Check real log tags and map bounds without saving or editing game content."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import afterdays
import event_runtime
import time

errors=[]
def hook(root,app):
    try:
        game=app.game;game.pop_events();app.fx.active=[]
        for effect in [dict(kind='money',amount=45),dict(kind='xp',amount=5),dict(kind='parts',amount=1,destination='bag'),dict(kind='money',amount=-1)]:
            event_runtime.apply(game,effect,{'title':'Test'})
        app.refresh();root.update_idletasks()
        assert app.logbox.tag_ranges('#9cdda8') and app.logbox.tag_ranges('#e56860')
        events=app.fx.active
        assert len(events)==4
        assert all(b['start']>=a['start']+a['duration']+.34 for a,b in zip(events,events[1:]))
        for e in events:e['start']=time.monotonic()+100
        events[0]['start']=time.monotonic()
        app.fx.render();root.update_idletasks()
        box=app.canvas.bbox('fx')
        assert box and box[0]>=0 and box[1]>=0
        assert box[2]<=app.canvas.winfo_width() and box[3]<=app.canvas.winfo_height()
        print('Colored log, serial notices and map bounds: OK')
    except Exception as exc:errors.append(exc)
    finally:root.destroy()

afterdays.launch(test_hook=hook)
if errors:raise errors[0]
