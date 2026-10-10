"""Exercise the real app's automatic radio window and its response buttons."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import ui.application as application
import game.model as afterdays

errors=[]

def hook(root,app):
    def check():
        try:
            app.game=afterdays.Game(5);app.game.prepare_campaign()
            app.game.step(1,0);app.game.step(1,0);app.refresh()
            root.after(1000,radio)
        except Exception as exc:errors.append(exc);root.destroy()
    def widgets(parent):
        for widget in parent.winfo_children():
            yield widget
            yield from widgets(widget)
    def radio():
        try:
            app.offer_notices();root.update_idletasks()
            assert app.dialog and app.dialog.winfo_class()=='Frame'
            assert app.dialog.master is app.canvas.master
            assert str(app.dialog.place_info()['in'])==str(app.canvas)
            assert app.dialog.winfo_toplevel() is root
            assert app.dialog.portrait.pack_info()['side']=='right'
            assert app.route.blocked()
            assert app.dialog.winfo_rooty()+app.dialog.winfo_height()<=app.canvas.winfo_rooty()+app.canvas.winfo_height()
            if len(sys.argv)>1:
                from PIL import ImageGrab
                root.after(350,root.quit);root.mainloop();root.update_idletasks()
                assert app.dialog.photo and app.dialog.portrait.winfo_ismapped()
                print('Portrait:',app.dialog.portrait.winfo_geometry(), 'overlay:',app.dialog.winfo_geometry())
                ImageGrab.grab(bbox=(root.winfo_rootx(),root.winfo_rooty(),root.winfo_rootx()+root.winfo_width(),root.winfo_rooty()+root.winfo_height())).save(sys.argv[1])
            buttons=[w for w in widgets(app.dialog) if w.winfo_class()=='Button']
            answer=next(w for w in buttons if str(w.cget('text')).startswith('Я не шукаю'))
            assert answer.winfo_height()>1
            xp=app.game.xp;answer.invoke();root.update_idletasks()
            assert app.game.xp==xp+5 and 0 in app.game.known_cities
            agree=next(w for w in widgets(app.dialog) if w.winfo_class()=='Button' and w.cget('text')=='Добре')
            agree.invoke();root.update_idletasks()
            assert app.game.reputation(0)==5
            assert app.game.story_states()['noise_in_the_wind']['index']==1
            assert app.dialog is None
            # Hero speech uses the opposite side; resizing keeps the overlay on the map.
            import dialogue_system,content
            from ui.dialogue_overlay import DialogueOverlay
            s=dialogue_system.Session(content.read('dialogues.json'),'demo_crossroads')
            s.choose('refuse');overlay=DialogueOverlay(app.quest_panel,s);root.update_idletasks()
            assert overlay.portrait.pack_info()['side']=='left'
            root.geometry('1100x760');root.update_idletasks()
            assert overlay.winfo_width()<=app.canvas.winfo_width()
            overlay.close();assert app.dialog is None
            print('In-map dialogue, NPC/hero portrait sides, resizing, replies and rewards: OK')
        except Exception as exc:errors.append(exc)
        finally:root.destroy()
    root.after(200,check)

application.launch(test_hook=hook)
if errors:raise errors[0]
