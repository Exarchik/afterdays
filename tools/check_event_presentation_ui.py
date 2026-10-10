"""Exercise real event windows without changing the player's save."""
from pathlib import Path
import sys
import traceback
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import afterdays
import game_dialogs
import tkinter as tk
from tkinter import ttk

errors=[]
def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)

def check(root,app):
    def failed(kind,value,tb):
        errors.append(''.join(traceback.format_exception(kind,value,tb)));root.destroy()
    root.report_callback_exception=failed
    g=app.game;g._events=[];g.loot=[];g.road_event=None
    g.road_event=dict(kind='ui_test',title='Покинутий сховок',body='У сховку знайдено припаси.',
        art='event_theme:camp',choices=[['take','Взяти нагороду']],
        definition=dict(title='Покинутий сховок',choices=[dict(id='take',text='Взяти нагороду',costs=[],outcomes=[dict(chance=1,effects=[
            dict(kind='xp',amount=5),dict(kind='money',amount=20),
            dict(kind='med',amount=4,destination='loot'),dict(kind='parts',amount=3,destination='bag')])])]))
    app.road_dialog()
    event_window=app.dialog
    assert app._event_loading and isinstance(event_window,tk.Toplevel)
    pos=(g.x,g.y)
    class Key:keysym='w'
    app.key(Key());assert (g.x,g.y)==pos
    def opened():
        assert not app._event_loading and isinstance(app.dialog,tk.Toplevel)
        assert app.dialog is event_window
        choices=[w for w in descendants(app.dialog) if isinstance(w,tk.Button) and w.cget('text')=='Взяти нагороду']
        assert len(choices)==1
        choices[0].invoke();root.after(150,result)
    def result():
        assert app.dialog and app.dialog.title()=='Покинутий сховок'
        assert app.dialog is event_window
        labels=[w.cget('text') for w in descendants(app.dialog) if isinstance(w,tk.Label)]
        assert 'Результати події' in labels
        assert 'Стани' in labels and 'Предмети' in labels
        assert any('XP' in text for text in labels)
        app.dialog.lift();app.dialog.focus_force();root.update()
        root.after(350,root.quit);root.mainloop()
        if len(sys.argv)>1:
            from PIL import ImageGrab
            win=app.dialog
            ImageGrab.grab(bbox=(win.winfo_rootx(),win.winfo_rooty(),win.winfo_rootx()+win.winfo_width(),win.winfo_rooty()+win.winfo_height())).save(sys.argv[1])
        app.dialog.close_dialog()
        app.dialog.lift();root.after(250,root.quit);root.mainloop()
        from adventure_ui import Storage
        storage=next(w for w in descendants(app.dialog) if isinstance(w,Storage))
        assert storage.source=='loot'
        item=next(i for i in g.loot if i['kind']=='med');storage.select(item['id'],'withdraw');storage.qty.set('2');storage.transfer()
        assert item['qty']==2
        root.update_idletasks()
        carried=next(i for i in g.bag if i['kind']=='med')
        storage.qty.set('1')
        storage.drop(dict(item=carried,direction='deposit'),storage.stored.canvas.winfo_rootx()+10,storage.stored.canvas.winfo_rooty()+10)
        assert sum(i.get('qty',1) for i in g.loot if i['kind']=='med')==3
        storage.collect_all();assert not g.loot
        app.dialog.close_dialog()
        # Synchronous confirmation must block keys and restore dialog state.
        def dismiss():
            assert isinstance(app.dialog,tk.Frame)
            next(w for w in descendants(app.dialog) if isinstance(w,ttk.Button) and w.cget('text')=='Ні').invoke()
        root.after(100,dismiss)
        assert game_dialogs.askyesno('Перевірка','Залишити предмети?',parent=root) is False
        assert app.dialog is None
        import battle_results,progression as p
        g.battle=dict(w=10,h=10,walls=[],pos=[1,1],enemies=[],ap=6,max_ap=6,round=1,
                      corpses=[],kills=[],region_level=1,biome='waste',entrance047=[1,1],faction_loot=[p.supply('credits',6)])
        battle_results.begin(g);battle_results.hit(g,'dealt',12,30);battle_results.hit(g,'received',5,30)
        g.gain_xp(4);g.victory();app.refresh()
        root.after(150,battle_result)
    def battle_result():
        labels=[w.cget('text') for w in descendants(app.dialog) if isinstance(w,tk.Label)]
        assert 'Результати битви' in labels and 'Стани' in labels and 'Предмети' in labels
        assert 'Нанесено шкоди: 12' in labels and 'Отримано шкоди: 5' in labels
        assert 'Отримано досвіду: 4 XP' in labels
        root.destroy()
    root.after(150,opened)

afterdays.launch(test_hook=check)
if errors:raise AssertionError('\n'.join(errors))
print('PASS: one event window for loading, choices and grouped result; local credits and loot transfer; combat result; themed confirmation.')
