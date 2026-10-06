"""Run the actual editor entry point, without importing afterdays first."""
import runpy
import sys
import tkinter as tk
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
errors=[]
def check(root,*args,**kwargs):
    root.report_callback_exception=lambda kind,error,trace:errors.append(error)
    try:
        root.update()
        editor=next(w for w in root.winfo_children() if hasattr(w,'humans'))
        assert editor.humans.current
        assert 'Приклад спорядження' in editor.humans.preview.get(),editor.humans.preview.get()
        editor.tabs.select(editor.humans)
        editor.humans.level.set('5');root.update()
        assert 'L5' in editor.humans.preview.get()
        editor.tabs.select(editor.factions)
        editor.factions.open('bandits');editor.factions.weight.set('60,5')
        assert editor.factions.commit()
        import copy,tempfile,entity_catalog
        from test_entity_editor import project_copy
        with tempfile.TemporaryDirectory() as folder:
            store=entity_catalog.Store(project_copy(folder));store.data=copy.deepcopy(editor.store.data)
            store._save()
            assert entity_catalog.Store(folder).data['factions']['factions']['bandits']['encounter_weight']==60.5
        editor.factions.open('settlers');root.update()
        assert editor.factions.weight.get()=='25'
        assert not errors,errors
        print('PASS: real editor entry point, faction weight field, decimal comma, save/reload, legacy default')
    finally:root.destroy()

sys.argv=[str(ROOT/'event_editor.py')]
with patch.object(tk.Tk,'mainloop',check):
    runpy.run_path(str(ROOT/'event_editor.py'),run_name='__main__')
