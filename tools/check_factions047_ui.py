"""Exercise editor forms, persistence, and the real battle renderer in isolation."""
import sys,copy,random,tempfile,tkinter as tk
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import ui.application as application
import game.model as afterdays
import content_editor
import entity_catalog
import faction_rules
from test_entity_editor import project_copy
from PIL import ImageGrab

def capture(root,name):
    root.update_idletasks()
    ImageGrab.grab(bbox=(root.winfo_rootx(),root.winfo_rooty(),root.winfo_rootx()+root.winfo_width(),root.winfo_rooty()+root.winfo_height())).save(Path(__file__).resolve().parents[1]/name)

with tempfile.TemporaryDirectory() as folder:
    project=project_copy(folder);root=tk.Tk();errors=[]
    root.report_callback_exception=lambda *args:errors.append(args[1])
    editor=content_editor.ContentEditor(root,project/'data/road_events.json',project)
    root.update()
    assert 'Люди' in [editor.tabs.tab(tab,'text') for tab in editor.tabs.tabs()]
    h=editor.humans;editor.tabs.select(h);h.open('human_bandit');h.fields['hp'].set('65');h.level.set('5');root.update()
    assert 'L5' in h.preview.get();assert h.commit()
    capture(root,'factions047-humans.png')
    with patch('faction_editor.simpledialog.askstring',return_value='Тестовий боєць'):h.add()
    new_human=h.current
    f=editor.factions;editor.tabs.select(f);f.open('bandits');root.update()
    assert new_human in f.members;f.members[new_human].set(True)
    f.relations['settlers'].set('Друзі');assert f.commit()
    assert editor.store.data['factions']['factions']['settlers']['relations']['bandits']=='friendly'
    capture(root,'factions047-factions.png')
    # Atomic catalog persistence (do not repack missing test-copy art assets).
    editor.store._save();again=entity_catalog.Store(project)
    assert again.data['factions']['humans']['human_bandit']['hp']==65
    assert new_human in again.data['factions']['factions']['bandits']['members']
    root.destroy();assert not errors,errors

errors=[]
def hook(root,app):
    root.report_callback_exception=lambda *args:errors.append(args[1])
    def check():
        try:
            g=afterdays.Game(47);g.start_battle();app.game=g
            b=g.battle;b['enemies']=[faction_rules.make_human(random.Random(3),'human_bandit','bandits',1,[8,5]),faction_rules.make_human(random.Random(4),'human_settler','settlers',1,[6,5])]
            b['walls']=[p for p in b['walls'] if p not in [[8,5],[6,5]]]
            app.refresh();root.update();capture(root,'factions047-battle.png')
            for e in b['enemies']:
                from ui.inspection import monster_text
                assert 'Фракція:' in monster_text(g,e)
            g._finish_enemy(b['enemies'][0]);g.check_faction_victory();app.refresh();root.update()
            assert b['safe_exit047'];assert 'безпечний' in app.hint.cget('text').lower()
            capture(root,'factions047-exit.png')
            assert 'v0.47' in root.title()
        except Exception as exc:errors.append(exc)
        finally:root.destroy()
    root.after(300,check)
application.launch(test_hook=hook)
if errors:raise errors[0]
print('PASS: human/faction editor, mutual relations, new membership, save/reload, battle rendering and safe exit.')
