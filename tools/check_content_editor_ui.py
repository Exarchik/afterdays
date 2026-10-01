"""Exercise all content-editor sections on temporary catalogs, never live data."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tempfile
import tkinter as tk
from tkinter import ttk
from unittest.mock import patch
from test_entity_editor import project_copy
from content_editor import ContentEditor
import entity_catalog as catalog

def run(capture=None):
    with tempfile.TemporaryDirectory() as folder:
        root_path=project_copy(folder)
        root=tk.Tk();ttk.Style(root).theme_use('clam')
        try:
            app=ContentEditor(root,root_path/'data/road_events.json',root_path);root.update()
            assert len(app.tabs.tabs())==9
            assert app.commit() and not app.store.dirty,'Opening unchanged sections must not alter catalogs'
            app.events.fields['title'].set('Тест спільного збереження')
            for section,panel in app.panels.items():
                app.tabs.select(panel);root.update();initial=len(app.store.items(section))
                before=panel.table.item(panel.table.get_children()[0])['values']
                panel.level.set('15');panel.refresh_preview();root.update()
                assert panel.table.get_children() and not panel.preview_error.get()
                with patch('entity_editor.simpledialog.askstring',return_value='Тестова модель '+section):panel.new()
                assert len(app.store.items(section))==initial+1
                panel.duplicate();assert len(app.store.items(section))==initial+2
                field={'weapon':'damage','armor':'defense','helmet':'defense','module':'base','monster':'hp'}[section]
                panel.fields[field].set('51');panel.refresh_preview();root.update()
                if section=='monster':
                    panel.fields['base_level'].set('7');panel.refresh_preview();root.update()
                    assert panel.level.get()=='7'
                assert panel.commit()
                if capture:
                    import time
                    from PIL import ImageGrab
                    root.lift();root.update();time.sleep(.4);root.update()
                    target=Path(capture);target.mkdir(parents=True,exist_ok=True)
                    ImageGrab.grab(bbox=(root.winfo_rootx(),root.winfo_rooty(),root.winfo_rootx()+root.winfo_width(),root.winfo_rooty()+root.winfo_height())).save(target/(section+'_editor.png'))
            assert app.save_all()
            loaded=catalog.Store(root_path)
            assert not loaded.validate()
            import event_catalog
            saved_events=event_catalog.load(root_path/'data/road_events.json')
            assert any(e['id']==app.events.current and e['title']=='Тест спільного збереження' for e in saved_events['events'])
            for section,panel in app.panels.items():assert loaded.data[catalog.GROUPS[section]][panel.current][{'weapon':'damage','armor':'defense','helmet':'defense','module':'base','monster':'hp'}[section]]==51
            panel=app.panels['weapon'];panel.fields['damage'].set('invalid')
            with patch('entity_editor.messagebox.showerror') as error:
                assert not app.save_all() and error.called
            print('Content editor UI: all sections, create, duplicate, preview, save/reload and validation passed')
        finally:root.destroy()

if __name__=='__main__':run(sys.argv[1] if len(sys.argv)>1 else None)
