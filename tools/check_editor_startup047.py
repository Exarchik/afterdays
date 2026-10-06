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
        assert not errors,errors
        print('PASS: event_editor.py __main__, human preview at levels 1 and 5, no game pre-import')
    finally:root.destroy()

sys.argv=[str(ROOT/'event_editor.py')]
with patch.object(tk.Tk,'mainloop',check):
    runpy.run_path(str(ROOT/'event_editor.py'),run_name='__main__')
