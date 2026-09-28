"""Regression: invoke the actual metro button with the actual App.popup method."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import metro035_ui


def popup_method():
    """Load the nested App method without starting a Tk main loop."""
    tree = ast.parse(Path(__file__).with_name('afterdays.py').read_text())
    app = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == 'App')
    method = next(n for n in app.body if isinstance(n, ast.FunctionDef) and n.name == 'popup')
    namespace = dict(tk=SimpleNamespace(Toplevel=lambda root: Window()), sprites=Mock(), PANEL='#000000')
    exec(compile(ast.Module(body=[method], type_ignores=[]), 'afterdays.py', 'exec'), namespace)
    return namespace['popup']


class Window:
    """Strict fake: missing custom methods raise just as on a real Toplevel."""
    def __init__(self):
        self.destroyed = False
        self.protocols = {}
        self.bindings = {}
    def title(self, value): pass
    def winfo_screenwidth(self): return 1920
    def winfo_screenheight(self): return 1080
    def geometry(self, value): pass
    def configure(self, **kwargs): pass
    def transient(self, root): pass
    def grab_set(self): pass
    def protocol(self, key, fn): self.protocols[key] = fn
    def bind(self, key, fn): self.bindings[key] = fn
    def destroy(self): self.destroyed = True


class MetroButtonTests(unittest.TestCase):
    def test_button_closes_popup_then_dispatches_current_action(self):
        """The old popup fails here with AttributeError before reaching metro_action."""
        popup = popup_method()
        q = dict(id='metro', title='Metro')
        game = Mock()
        game.metro_parent.return_value = q
        game.metro_local.return_value = [q]
        game.quest_text.return_value = 'Instructions'
        game.quest_item_views.return_value = []
        app = SimpleNamespace(game=game, route=Mock(), root=Mock(), refresh=Mock(), dialog=None)
        app.popup = lambda title, geometry: popup(app, title, geometry)
        def dispatch(fn):
            self.assertIsNone(app.dialog)
            self.assertTrue(win.destroyed)
            fn()
        app.act = dispatch
        buttons = []
        def button(parent, **kwargs):
            buttons.append(kwargs['command'])
            return Mock()
        with patch.object(metro035_ui.tk, 'Label'), patch.object(metro035_ui.tk, 'Text'), \
             patch.object(metro035_ui.tk, 'Canvas'), patch.object(metro035_ui.ttk, 'Button', side_effect=button):
            metro035_ui.show(app, 'metro')
            win = app.dialog
            self.assertIs(win.close_dialog, win.protocols['WM_DELETE_WINDOW'])
            self.assertEqual(len(buttons), 1)
            buttons[0]()
        game.metro_action.assert_called_once_with('metro')
        app.refresh.assert_called_once()


if __name__ == '__main__': unittest.main()
