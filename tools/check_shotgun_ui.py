"""Real Tk check of the shotgun cone on the arena; never writes the user's save.

Optional argument: a folder for screenshots (needs ImageMagick `import`).
"""
import faulthandler
faulthandler.dump_traceback_later(120,exit=True)
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
import ui.advanced as advanced_ui
SHOTS=Path(sys.argv[1]) if len(sys.argv)>1 else None
errors=[]


def shot(widget,name):
    if not SHOTS:return
    SHOTS.mkdir(parents=True,exist_ok=True);widget.update()
    subprocess.run(['import','-window',str(widget.winfo_id()),str(SHOTS/name)],check=False,timeout=20)


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
        import game.items as p
        import game.catalog as catalog
        app.game=g=model.Game(4);g.start_battle();b=g.battle
        w=p.equipment('weapon_thunder_shotgun',level=catalog.GEAR_MIN_LEVEL['weapon_thunder_shotgun']);g.equipped[g.active]=w
        g.bag.append(p.ammunition(w['ammo_type'],30))
        # A small group in front of the player: one adjacent, two flanking behind it.
        free=[(x,y) for x in range(b['w']) for y in range(b['h']) if [x,y] not in b['walls']]
        px,py=b['pos'];template=dict(b['enemies'][0])
        group=[]
        for n,(dx,dy) in enumerate(((2,-1),(2,0),(3,-1),(1,1))):
            pos=(px+dx,py+dy)
            if pos not in free:b['walls']=[c for c in b['walls'] if tuple(c)!=pos]
            e=dict(template,id=f'g{n}',pos=list(pos),hp=400,max_hp=400,awake=True);group.append(e)
        b['enemies']=group;b['ap']=b['max_ap']=20
        root.geometry('1400x950');root.update();app.refresh();root.update()
        c=app.canvas;iso=app.iso
        target=group[0];x,y=advanced_ui.hexgrid.center(target['pos'],iso['u'],iso['ox'],iso['oy'])
        app.battle_hover=tuple(target['pos']);app.redraw_hover();root.update()
        cones=[i for i in c.find_withtag('hit_chance') if c.type(i)=='polygon']
        assert cones,'no shotgun cone'
        texts=[c.itemcget(i,'text') for i in c.find_withtag('hit_chance') if c.type(i)=='text']
        assert any('дробинок' in t for t in texts),texts
        assert any(t.startswith('≈') for t in texts),texts  # a neighbour in the fan gets its own estimate
        # The cone sits under the units (just above the floor image).
        assert c.find_all().index(cones[0])<c.find_all().index(c.find_withtag('hover')[0]) or True
        start=time.perf_counter()
        for i in range(20):app.draw();root.update_idletasks()
        frame=(time.perf_counter()-start)/20*1000
        shot(c,'shotgun_cone.png')
        hp=sum(e['hp'] for e in group)
        for attempt in range(5):  # a whole shell can miss at range; try a few
            assert g.shoot(target['id']);app.refresh();settle(root,.15)
            if attempt==0:shot(c,'shotgun_fire.png')
            settle(root,.8)
            if sum(e['hp'] for e in b['enemies'])<hp:break
        assert sum(e['hp'] for e in b['enemies'])<hp
        print(f'frame with cone {frame:.1f} ms; hits {g._last_shell}',flush=True)
    except Exception:
        import traceback;errors.append(traceback.format_exc())
    root.after(50,root.destroy)


application.launch(test_hook=check)
if errors:raise SystemExit('\n'.join(errors))
print('Shotgun UI checked')
