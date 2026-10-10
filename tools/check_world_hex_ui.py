"""Real Tk smoke check; never writes the user's save."""
import faulthandler
faulthandler.dump_traceback_later(60)
import hashlib
import sys
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import ui.application as application
import game.model as afterdays
from tkinter import messagebox
messagebox.showinfo=lambda *args,**kwargs: None

errors=[]
def check(root,app):
    def failure(*args):
        errors.append(str(args));root.destroy()
    root.report_callback_exception=failure
    try:
        root.attributes("-topmost",True)
        root.update_idletasks()
        app.refresh()
        assert app.canvas.find_withtag('world_hex')
        assert app.canvas.find_withtag('world_terrain')
        view=app.world_view
        assert view.cell(*view.point((app.game.x,app.game.y)))==(app.game.x,app.game.y)
        save=Path.home()/'Afterdays'/'save.json'
        if save.exists():
            digest=hashlib.sha256(save.read_bytes()).hexdigest()
            app.game=afterdays.Game.load(save)
            app.refresh()
            assert app.canvas.find_withtag('world_hex')
            assert hashlib.sha256(save.read_bytes()).hexdigest()==digest
        app.draw();ids=app.canvas.find_withtag('world_hex')
        overlay_ids=app.canvas.find_withtag('world_overlay')
        app.draw()
        assert ids==app.canvas.find_withtag('world_hex')
        assert overlay_ids==app.canvas.find_withtag('world_overlay')
        app.canvas.delete('all');app.draw()
        assert app.canvas.find_withtag('world_hex') and ids!=app.canvas.find_withtag('world_hex')
        root.update()
        from PIL import ImageGrab
        target=Path(tempfile.gettempdir())/'afterdays-hex-world.png'
        ImageGrab.grab(window=root.winfo_id()).save(target)
        print('Screenshot:',target,flush=True)
        if app.dialog:app.dialog.close_dialog()
        print('Opening atlas',flush=True)
        app.atlas();root.update()
        assert app.dialog
        app.dialog.close_dialog()
        print("Opening battle",flush=True)
        app.game.start_battle();app.refresh();root.update()
        assert app.game.battle and hasattr(app,'iso')
        app.game.battle=None;app.refresh();root.update()
        assert app.canvas.find_withtag('world_hex')
        print('PASS: new game, existing save, hit testing, atlas, combat; save unchanged',flush=True)
    except Exception:
        import traceback
        errors.append(traceback.format_exc())
    finally:
        root.destroy()

application.launch(test_hook=check)
if errors:
    print('\n'.join(errors));raise SystemExit(1)
