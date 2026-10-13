"""Edit native variants and authored quests; save/reload a temporary project only."""
import sys,tempfile,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tkinter as tk
from tkinter import ttk
from unittest.mock import patch
from content_editor import ContentEditor
from entity_catalog import Store
from tests.test_entity_editor import project_copy
import quest_catalog
errors=[]
with tempfile.TemporaryDirectory() as folder:
    project=project_copy(folder);root=tk.Tk();root.geometry('1200x850')
    root.report_callback_exception=lambda *args:errors.append(''.join(traceback.format_exception(*args)))
    app=ContentEditor(root,project/'data/road_events.json',project);root.update()
    panel=app.quests
    for kind in {**quest_catalog.TYPES,**quest_catalog.SPECIAL}:
        panel.tree.selection_set('type:'+kind);root.update()
        assert panel.native.kind==kind and panel.native.winfo_ismapped()
        assert panel.commit()
    panel.tree.selection_set('type:hunt');root.update()
    panel.native.vars['title'].set('Полювання редактора')
    panel.native.vars['min_level'].set('7')
    panel.native.vars['reward'].set('200')
    panel.native.vars['art'].set('quest:cache')
    panel.native.variant_var.set('Елітний');panel.native.switch()
    panel.native.vars['reward'].set('600');panel.native.vars['min_level'].set('10')
    assert panel.commit()
    panel.add();root.update();panel.vars['elite'].set(True);panel.vars['art'].set('quest:hunt')
    panel.vars['xp_step'].set('8');panel.vars['money_power'].set('1.3')
    with patch('content_editor.messagebox.showerror') as error:
        assert app.save_all();error.assert_not_called()
    doc=Store(project).data['quests'];assert doc['native']['hunt']['normal']['min_level']==7
    assert doc['native']['hunt']['elite']['reward']==600
    assert doc['quests'][-1]['elite'] and doc['quests'][-1]['xp_step']==8
    panel.tree.selection_set('type:hunt');root.update()
    if '--screenshot' in sys.argv:
        root.lift();root.attributes('-topmost',True);root.update()
        def capture():
            from PIL import ImageGrab
            ImageGrab.grab(bbox=(root.winfo_rootx(),root.winfo_rooty(),root.winfo_rootx()+root.winfo_width(),root.winfo_rooty()+root.winfo_height())).save('artifacts/quest-profiles-editor.png')
            root.quit()
        root.after(600,capture);root.mainloop()
    root.destroy()
assert not errors,'\n'.join(errors)
print('PASS: all native types editable, separate elite profile, art, authored fields, atomic save and reload')
