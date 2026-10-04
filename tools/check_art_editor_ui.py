"""Validate import/crop/gallery/save and normal game PNG rendering in an isolated project."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tempfile
import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace
from unittest.mock import patch
from test_entity_editor import project_copy
from test_art_editor import fixture
from content_editor import ContentEditor
from event_editor import ArtDialog
import art_editor
import sprites

def run(capture=None):
    with tempfile.TemporaryDirectory() as folder:
        project=project_copy(folder);source=project/'sample.png';fixture().save(source)
        root=tk.Tk();ttk.Style(root).theme_use('clam')
        def shot(widget,name):
            if not capture:return
            import time
            from PIL import ImageGrab
            widget.lift();root.update();time.sleep(.5);root.update()
            ImageGrab.grab(bbox=(widget.winfo_rootx(),widget.winfo_rooty(),widget.winfo_rootx()+widget.winfo_width(),widget.winfo_rooty()+widget.winfo_height())).save(Path(capture)/name)
        try:
            app=ContentEditor(root,project/'data/road_events.json',project);root.update()
            assert len(app.tabs.tabs())==10
            app.tabs.select(app.arts);root.update()
            def interact(dialog):
                root.update();dialog.name.set('Тестовий арт');dialog.group.set('Події')
                ox,oy=dialog.offset;sx,sy=dialog.scale
                dialog.start_crop(SimpleNamespace(x=ox+60*sx,y=oy+30*sy))
                dialog.end_crop(SimpleNamespace(x=ox+270*sx,y=oy+180*sy))
                dialog.rotation.set('90');dialog.mirror.set(True);dialog.render();root.update()
                assert not dialog.error.get();assert dialog.preview_photo.width()==192
                assert dialog.settings()['crop']==[60,30,270,180]
                shot(dialog,'art_edit_dialog.png')
                result=dialog.read();dialog.destroy();return result
            with patch('art_editor.filedialog.askopenfilename',return_value=str(source)),patch.object(art_editor.ArtEditDialog,'show',interact):app.arts.import_file()
            key=app.arts.current;assert key.startswith('art_custom_') and key in app.store.art
            source_path='assets/'+app.library.entries[key]['editor_source']
            sources=app.library.imported_sources()
            assert sum(row['path']==source_path for row in sources)==1
            picker=art_editor.ImportedSourceDialog(root,app.library);root.update()
            picker.query.set('Тестовий арт');root.update()
            assert picker.read()==source_path and picker.preview_photo.width()>0
            picker.query.set('no-such-source-123');root.update()
            assert not picker.list.get_children();picker.destroy()
            from PIL import Image
            replacement=art_editor.ArtEditDialog(root,Image.new('RGBA',(20,20),'blue'),'Незмінна назва',settings=dict(art_editor.art.DEFAULTS,crop=[0,0,10,10]))
            with patch.object(art_editor.ImportedSourceDialog,'show',return_value=None):replacement.choose_imported()
            assert replacement.source.size==(20,20) and replacement.crop_enabled.get()
            with patch.object(art_editor.ImportedSourceDialog,'show',return_value=source_path):replacement.choose_imported()
            root.update();replacement.render()
            assert replacement.source.tobytes()==fixture().tobytes()
            assert not replacement.crop_enabled.get() and replacement.name.get()=='Незмінна назва'
            assert [int(v.get()) for v in replacement.coords]==[0,0,320,200]
            before_sources={p for p in app.store.pending_assets if '/sources/' in p}
            app.library.stage('art_source_reuse_test',*replacement.read());replacement.destroy()
            assert before_sources=={p for p in app.store.pending_assets if '/sources/' in p}
            root.update();shot(root,'art_library_editor.png')
            gallery=ArtDialog(root,key);root.update();assert key in gallery.keys
            gallery.query.set('Тестовий арт');assert key in gallery.filtered();gallery.destroy()
            app.events.fields['art'].set(key);assert app.events.commit()
            panel=app.panels['weapon'];panel.art.set(key);assert panel.commit()
            assert app.save_all()
            # Exercise the unchanged runtime atlas and inventory loaders, not the editor provider.
            del root._editor_art_library
            with patch.object(sprites,'MANIFEST',app.store.art),patch.object(sprites,'ROOT',project/'assets'):
                photo=sprites.photo(root,key,192);assert photo is not None and photo.width()==192
                photo=sprites.inventory_photo(root,{'art_id':key},96);assert photo is not None and (photo.width(),photo.height())==(96,72)
            root._editor_art_library=app.library
            app.destroy()
            reloaded=ContentEditor(root,project/'data/road_events.json',project);root.update()
            assert key in reloaded.library.entries
            print('Art editor UI: imported-source gallery, search, cancel, source reuse without duplication, crop reset, atlas save/reload and game rendering passed')
        finally:root.destroy()

if __name__=='__main__':run(sys.argv[1] if len(sys.argv)>1 else None)
