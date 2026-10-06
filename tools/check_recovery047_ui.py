"""Exercise equipment cards, both map markers, and recoverable grave inventory."""
import sys,random
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import afterdays,faction_rules,progression as p
from update046 import credit_item
errors=[]
def screenshot(root,name):
    from PIL import ImageGrab
    root.lift();root.update()
    root.after(350,root.quit);root.mainloop()
    root.update_idletasks()
    ImageGrab.grab(bbox=(root.winfo_rootx(),root.winfo_rooty(),root.winfo_rootx()+root.winfo_width(),root.winfo_rooty()+root.winfo_height())).save(Path(__file__).resolve().parents[1]/name)

def hook(root,app):
    root.report_callback_exception=lambda kind,error,trace:errors.append(error)
    def check():
        try:
            g=afterdays.Game(47);app.game=g
            g.graves.append(dict(id='test',pos=[g.x+1,g.y],items=[p.supply('med',3),credit_item(70)],turn=0))
            app.refresh();root.update()
            assert app.canvas.find_withtag('respawn_flag');assert app.canvas.find_withtag('grave_marker')
            screenshot(root,'recovery047-map.png')
            g.x+=1;assert g.search()
            import recovery_ui
            recovery_ui.show(app);root.update();assert app.dialog
            screenshot(app.dialog,'recovery047-grave.png')
            app.dialog.close_dialog();g._grave_request=False
            assert g.collect_all_graves();app.refresh();root.update();assert not app.canvas.find_withtag('grave_marker')
            g.start_battle();b=g.battle
            actor=faction_rules.make_human(random.Random(1),'human_bandit','bandits',1,[8,5]);actor['awake']=False;b['enemies']=[actor]
            app.refresh();root.update()
            from inspection_ui import inspect_monster,monster_text
            assert 'Відпочиває' in monster_text(g,actor)
            assert 'Спорядження (кожен предмет' not in monster_text(g,actor)
            old_cell=app.cell;app.cell=lambda event:tuple(actor['pos'])
            inspect_monster(app,SimpleNamespace());app.cell=old_cell;root.update()
            screenshot(app.dialog,'recovery047-human.png');app.dialog.close_dialog()
            assert not errors,errors
            print('PASS: world markers, grave dialog and recovery, resting state, illustrated human equipment')
        except Exception as exc:errors.append(exc)
        finally:root.destroy()
    root.after(300,check)
afterdays.launch(test_hook=hook)
if errors:raise errors[0]
