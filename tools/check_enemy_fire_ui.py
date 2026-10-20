"""Real Tk check of enemy attack animations (every monster and an armed person); never writes the save.

Optional argument: a folder for screenshots (needs ImageMagick `import`).
"""
import faulthandler
faulthandler.dump_traceback_later(240,exit=True)
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
        import content
        import game.model as model
        import game.items as p
        app.game=g=model.Game(4);g.start_battle();b=g.battle
        root.geometry('1400x950');root.update()
        template=dict(b['enemies'][0]);px,py=b['pos']
        cases=[(ident,dict(template,id=ident,type_id=ident,kind=content.MONSTER_IDS.index(ident),range=content.MONSTER_DATA[ident]['range'])) for ident in content.MONSTER_DATA]
        human=dict(template,id='human',human=True,range=5,equipment=dict(weapon=p.equipment('weapon_rust_assault')),faction='bandits')
        cases.append(('human_rifle',human))
        for name,actor in cases:
            if g.battle is None:g.start_battle()
            b=g.battle;px,py=b['pos']
            reach=min(3,actor['range']);pos=[px+reach,py]
            b['walls']=[c for c in b['walls'] if list(c)!=pos]
            actor.update(pos=pos,speed=0,hp=999,max_hp=999,awake=True,damage=1,attack=0,level=1)
            b['enemies']=[actor];g.hp=g.max_hp;app.fx.active=[];app.fx.pending=[];g.pop_events()
            app.refresh();root.update()
            with patch.object(g.rng,'randrange',return_value=99),patch.object(g.rng,'random',return_value=.99),patch.object(g,'protection_stat',return_value=0):
                g.end_turn()
            app.fx.ingest()
            blows=[e for e in app.fx.active if e['kind'] in ('attack','slash')]
            assert blows and ('attack_style' in blows[0] or 'damage_type' in blows[0]),(name,blows)
            blow=blows[0]
            from ui.projectiles import arrive
            for label,k in (('fly',arrive(blow)*.6),('hit',arrive(blow)+(1-arrive(blow))*.4)):
                with patch('time.monotonic',return_value=blow['start']+blow['duration']*k):app.fx.render()
                assert app.canvas.find_withtag('fx'),(name,label)
                shot(app.canvas,f'enemy_{name}_{label}.png')
                if SHOTS:
                    with open(SHOTS/'boxes.txt','a') as f:f.write(f"enemy_{name}_{label} {app.canvas.bbox('fx')}\n")
        print(f'{len(cases)} enemy attacks rendered',flush=True)
    except Exception:
        import traceback;errors.append(traceback.format_exc())
    root.after(50,root.destroy)


application.launch(test_hook=check)
if errors:raise SystemExit('\n'.join(errors))
print('Enemy fire UI checked')
