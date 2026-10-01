"""Exercise quest creation, validation and shared save/reload on temporary data."""
import sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tkinter as tk
from tkinter import ttk
from unittest.mock import patch
from test_entity_editor import project_copy
from content_editor import ContentEditor
from entity_catalog import Store

with tempfile.TemporaryDirectory() as folder:
    project=project_copy(folder);root=tk.Tk();ttk.Style(root).theme_use('clam')
    try:
        app=ContentEditor(root,project/'data/road_events.json',project);root.update()
        assert app.tabs.tab(0,'text')=='Квести'
        assert len(app.tabs.tabs())==9
        panel=app.quests;panel.add();root.update()
        first=panel.current;panel.vars['title'].set('Караван потребує допомоги')
        panel.vars['kind'].set('supplies — Постачання');panel.vars['min_level'].set('2');panel.vars['min_reputation'].set('25')
        panel.description.insert('1.0','Підготуйте припаси для наступного каравану.')
        assert panel.commit();panel.duplicate();root.update()
        panel.vars['title'].set('Друга доставка');panel.vars['requires'].set(first)
        panel.vars['repeatable'].set(True);panel.vars['cooldown'].set('80')
        with patch('content_editor.messagebox.showerror') as errors:
            assert app.save_all();errors.assert_not_called()
        loaded=Store(project);assert len(loaded.data['quests']['quests'])==2
        assert loaded.data['quests']['quests'][1]['requires']==[first]
        assert not loaded.dirty
        panel.vars['reward'].set('-10')
        with patch('quest_editor.messagebox.showerror') as errors:
            assert not app.save_all();errors.assert_called_once()
        panel.vars['reward'].set('150');assert panel.commit()
        panel.tree.selection_set('type:metro');root.update()
        assert panel.current is None
        panel.open(first);root.update()
        if len(sys.argv)>1:
            from PIL import ImageGrab
            root.lift();root.update()
            ImageGrab.grab(bbox=(root.winfo_rootx(),root.winfo_rooty(),root.winfo_rootx()+root.winfo_width(),root.winfo_rooty()+root.winfo_height())).save(sys.argv[1])
        app.destroy();app=ContentEditor(root,project/'data/road_events.json',project);root.update()
        assert len(app.quests.document['quests'])==2 and app.commit()
        print('Quest editor UI: passed (first tab, create, duplicate, conditions, validation, save, reload)')
    finally:root.destroy()
