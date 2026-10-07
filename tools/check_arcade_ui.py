"""Real OpenGL smoke test; does not load or write the user's save."""
import json,random,sys,tempfile,traceback,time,statistics
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import afterdays
errors=[]


def hook(root,app):
    root.lift()
    root.attributes('-topmost',True)
    def report(kind,error,tb):
        traceback.print_exception(kind,error,tb)
        errors.append(error)
        root.after_idle(root.destroy)
    root.report_callback_exception=report

    def world():
        try:
            if app.dialog:
                close=getattr(app.dialog,'close_dialog',app.dialog.destroy)
                close()
                app.dialog=None
            app.game=afterdays.Game(47)
            app.refresh()
            c=app.canvas
            assert c.window is not None
            c.render_now()
            assert c.metrics['textures']>0,c.metrics
            assert c.find_withtag('respawn_flag')
            assert c.find_withtag('world_player_ring')
            capture('world')
            print('WORLD',json.dumps(c.metrics))
            # Representative fully visible middle-of-map viewport, warm caches.
            app.show_full_map=True
            app.game.x,app.game.y=24,16
            rng=app.game.rng.getstate()
            samples=[]
            for n in range(25):
                begin=time.perf_counter()
                app.draw()
                c.render_now()
                if n>=5:samples.append((time.perf_counter()-begin)*1000)
            assert rng==app.game.rng.getstate(),'Rendering changed gameplay RNG'
            print('WARM_WORLD median_ms',round(statistics.median(samples),2),'batches',c.metrics['batches'])
            # Dispatch a real pyglet callback through the host's Tk bindings.
            seen=[]
            ident=c.bind('<Motion>',lambda e:seen.append((e.x,e.y)),add='+')
            c.window.on_mouse_motion(30,c.winfo_height()-40,0,0)
            assert seen==[(30,40)],seen
            c.unbind('<Motion>',ident)
            c.focus_force()
            c.window.on_key_press(c.pyglet.window.key.I,0)
            assert app.tabs.select()==str(app.inv_tab),'Keyboard did not reach game bindings'
            app.tabs.select(0)
            root.geometry('1400x940')
            root.after(300,battle)
        except Exception as exc:
            report(type(exc),exc,exc.__traceback__)

    def capture(name):
        from PIL import ImageGrab
        output=Path(tempfile.gettempdir())/('afterdays-arcade-'+name+'.png')
        root.update_idletasks()
        ImageGrab.grab(bbox=(root.winfo_rootx(),root.winfo_rooty(),root.winfo_rootx()+root.winfo_width(),root.winfo_rooty()+root.winfo_height())).save(output)
        print('SCREENSHOT',output)

    def battle():
        try:
            c=app.canvas
            assert abs(c.window.width-c.winfo_width())<=1
            app.game.start_battle()
            import faction_rules
            actor=faction_rules.make_human(random.Random(1),'human_bandit','bandits',1,[8,5])
            actor['awake']=False
            app.game.battle['enemies']=[actor]
            app.refresh()
            c.render_now()
            assert app.iso['sprites']
            print('BATTLE',json.dumps(c.metrics))
            # Existing modal windows must remain usable with the native child.
            app.help=lambda:None
            import tkinter as tk
            overlay=tk.Frame(c.master,bg='#00ff00')
            overlay.place(in_=c,x=20,y=20,width=120,height=80)
            overlay.lift()
            def finish():
                try:
                    from PIL import ImageGrab
                    image=ImageGrab.grab()
                    px,py=overlay.winfo_rootx()+40,overlay.winfo_rooty()+40
                    capture('overlay')
                    assert image.getpixel((px,py))[:3]==(0,255,0),'Tk overlay hidden by GL child'
                    overlay.destroy()
                    root.after(200,finish_battle)
                except Exception as exc:
                    report(type(exc),exc,exc.__traceback__)
            root.after(400,finish)
        except Exception as exc:
            report(type(exc),exc,exc.__traceback__)
    def finish_battle():
        capture('battle')
        print('PASS: GPU world, arena, resize, input forwarding, Tk overlay, clean shutdown')
        root.destroy()
    root.after(400,world)


afterdays.launch(test_hook=hook,renderer='arcade')
if errors:raise errors[0]
