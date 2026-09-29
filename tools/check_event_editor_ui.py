"""Exercise actual Tk editor widgets on an isolated catalog, optionally capture previews."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import copy
import tempfile
import tkinter as tk
from tkinter import ttk
from unittest.mock import patch
import event_catalog as c
from event_editor import Editor, ArtDialog, ChoiceDialog, EffectDialog, OutcomeDialog

def run(capture=False):
    with tempfile.TemporaryDirectory() as folder:
        path=Path(folder)/'events.json'; c.save(c.DOCUMENT,path)
        root=tk.Tk(); ttk.Style(root).theme_use('clam')
        try:
            editor=Editor(root,path); root.update()
            initial=len(editor.document['events'])
            editor.open_event('wounded'); root.update()
            if capture:
                from PIL import ImageGrab
                def shot(widget,name):
                    import time
                    widget.lift(); root.update(); time.sleep(.5); root.update()
                    ImageGrab.grab(bbox=(widget.winfo_rootx(),widget.winfo_rooty(),widget.winfo_rootx()+widget.winfo_width(),widget.winfo_rooty()+widget.winfo_height())).save(c.ROOT/name)
                shot(root,'event_editor_preview.png')
            editor.fields['title'].set('Змінена подія'); editor.fields['art'].set('event_theme:water')
            editor.choices[0]['outcomes'][0]['effects']=[dict(kind='xp',amount=47)]
            assert editor.save(); stored=c.load(path)
            edited=next(e for e in stored['events'] if e['id']=='wounded')
            assert edited['title']=='Змінена подія' and edited['art']=='event_theme:water'
            assert edited['choices'][0]['outcomes'][0]['effects'][0]['amount']==47
            with patch('event_editor.simpledialog.askstring',return_value='Нова тестова подія'): editor.new()
            assert len(editor.document['events'])==initial+1
            editor.duplicate(); assert len(editor.document['events'])==initial+2; assert editor.save()
            gallery=ArtDialog(root,'event_theme:camp'); root.update()
            assert len(gallery.keys)>16
            if capture: shot(gallery,'event_gallery_preview.png')
            gallery.query.set('water'); gallery.pick('event_theme:water'); assert gallery.read()=='event_theme:water'; gallery.destroy()
            effect=EffectDialog(root,dict(kind='ammo',amount=6,per_level=2,ammo='energy')); root.update()
            assert effect.read()['per_level']==2
            if capture: shot(effect,'event_effect_preview.png')
            effect.destroy()
            choice=ChoiceDialog(root,edited['choices'][0]); root.update(); assert choice.read()['id']=='help'; choice.destroy()
            outcome=OutcomeDialog(root); root.update(); assert outcome.read()['chance']==1; outcome.destroy()
            if capture:
                import afterdays,adventure_ui
                from types import SimpleNamespace
                game=afterdays.Game(1);game.make_road_event('wounded')
                def popup(title,size):
                    win=tk.Toplevel(root);win.title(title);win.geometry(size);return win
                app=SimpleNamespace(game=game,popup=popup,refresh=lambda:None)
                adventure_ui.road_window(app);root.update()
                win=[w for w in root.winfo_children() if isinstance(w,tk.Toplevel)][0]
                shot(win,'event_game_preview.png');win.destroy()
            editor.fields['weight'].set('invalid'); before=path.read_bytes()
            with patch('event_editor.messagebox.showerror') as error:
                assert not editor.save(); assert error.called
            assert path.read_bytes()==before
            print('Editor UI: passed (edit, add, duplicate, art, effects, save/reload, invalid-input protection)')
        finally: root.destroy()

if __name__=='__main__': run('--capture' in sys.argv)
