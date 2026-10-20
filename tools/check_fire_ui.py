"""Real Tk check of burst fire and projectile animations by damage type; never writes the save.

Optional argument: a folder for screenshots (needs ImageMagick `import`).
"""
import faulthandler
faulthandler.dump_traceback_later(180,exit=True)
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch
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


def check(root,app):
    def failure(*args):
        errors.append(str(args));root.destroy()
    root.report_callback_exception=failure
    try:
        app.show_notice=lambda *args,**kwargs: None
        import game.model as model
        import game.items as p
        import game.catalog as catalog
        import game.systems.adventure as adventure
        app.game=g=model.Game(4);g.start_battle();b=g.battle
        w=p.equipment('weapon_rust_assault',level=catalog.GEAR_MIN_LEVEL['weapon_rust_assault']);g.equipped[g.active]=w
        g.bag.append(p.ammunition(w['ammo_type'],300));w['fire_mode']='burst'
        px,py=b['pos'];template=dict(b['enemies'][0]);group=[]
        for n,(dx,dy) in enumerate(((3,-1),(3,0),(4,-2))):
            pos=(px+dx,py+dy);b['walls']=[c for c in b['walls'] if tuple(c)!=pos]
            group.append(dict(template,id=f'g{n}',pos=list(pos),hp=5000,max_hp=5000,awake=True))
        b['enemies']=group;b['ap']=b['max_ap']=200
        root.geometry('1400x950');root.update();app.refresh();root.update()
        c=app.canvas;iso=app.iso;target=group[0]
        x,y=advanced_ui.hexgrid.center(target['pos'],iso['u'],iso['ox'],iso['oy'])
        app.battle_hover=tuple(target['pos']);app.redraw_hover();root.update()
        texts=[c.itemcget(i,'text') for i in c.find_withtag('hit_chance') if c.type(i)=='text']
        assert any('куль черги' in t for t in texts),texts
        assert len([i for i in c.find_withtag('hit_chance') if c.type(i)=='polygon'])>=2
        shot(c,'burst_cone.png')
        original=dict(adventure.WEAPON_DAMAGE)
        try:
            for kind in ('kinetic','piercing','thermal','energy','electric'):
                adventure.WEAPON_DAMAGE[w['type_id']]=kind
                app.fx.active=[];g.pop_events()
                assert g.shoot(target['id'])
                app.fx.ingest()
                shots=[e for e in app.fx.active if e['kind']=='attack']
                assert len(shots)==5 and all(e['damage_type']==kind for e in shots),[e.get('damage_type') for e in shots]
                start=min(e['start'] for e in shots)
                for label,offset in (('fly',.17),('hit',.62)):
                    with patch('time.monotonic',return_value=start+offset):app.fx.render()
                    items=len(c.find_withtag('fx'));assert items>0,(kind,label)
                    shot(c,f'fire_{kind}_{label}.png')
        finally:
            adventure.WEAPON_DAMAGE.clear();adventure.WEAPON_DAMAGE.update(original)
        print('burst and projectiles rendered',flush=True)
    except Exception:
        import traceback;errors.append(traceback.format_exc())
    root.after(50,root.destroy)


application.launch(test_hook=check)
if errors:raise SystemExit('\n'.join(errors))
print('Fire UI checked')
