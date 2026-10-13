"""Shared nine-slice skin for game windows, independent of their content layout."""
from functools import lru_cache
from pathlib import Path
import tkinter as tk
from tkinter import ttk

BG = '#141c19'
GOLD = '#d4b477'
TEXT = '#d9d3bf'
ASSET = Path(__file__).resolve().parents[1] / 'assets/ui/results-panel.png'


@lru_cache(maxsize=1)
def source_image():
    try:
        from PIL import Image
        with Image.open(ASSET) as image:
            return image.convert('RGB')
    except (ImportError, OSError):
        return None


def panel_image(width, height):
    """Keep corners at a fixed size; stretch edges only along their length."""
    source = source_image()
    if source is None:
        return None
    from PIL import Image
    width, height = max(1, int(width)), max(1, int(height))
    result = Image.new('RGB', (width, height), BG)
    sw, sh = source.size
    cut = 48
    edge = min(24, width // 2, height // 2)
    xs, ys = (0, cut, sw-cut, sw), (0, cut, sh-cut, sh)
    dx, dy = (0, edge, width-edge, width), (0, edge, height-edge, height)
    for row in range(3):
        for col in range(3):
            size = dx[col+1]-dx[col], dy[row+1]-dy[row]
            if min(size) > 0:
                part = source.crop((xs[col], ys[row], xs[col+1], ys[row+1]))
                result.paste(part.resize(size, Image.Resampling.LANCZOS), (dx[col], dy[row]))
    return result


class WindowSkin:
    def __init__(self, window, compact=False):
        self.window = window
        self.job = None
        self.size = None
        self.photo = None
        self.seen = set()
        self.surfaces = {}
        self.background = None
        pad = 7 if compact else 14
        window.configure(bg=BG, padx=pad, pady=pad)
        self.canvas = tk.Canvas(window, bg=BG, highlightthickness=0, takefocus=False)
        self.canvas._window_decoration = True
        self.canvas.place(x=-pad, y=-pad, relwidth=1, relheight=1,
                          width=2*pad, height=2*pad)
        # Canvas.lower is an item operation; use the Tk widget stacking command.
        window.tk.call('lower', self.canvas._w)
        style = ttk.Style(window)
        if 'Survival.border' not in style.element_names():
            style.element_create('Survival.border', 'from', 'clam', 'Button.border')
        style.layout('Survival.TButton', [('Survival.border', {'sticky': 'nswe', 'children': [
            ('Button.padding', {'sticky': 'nswe', 'children': [
                ('Button.label', {'sticky': 'nswe'})]})]})])
        style.configure('Survival.TButton', foreground=TEXT, background='#322e20',
                        bordercolor='#8a7045', padding=(10, 6), font=('Segoe UI', 10))
        style.map('Survival.TButton', background=[('active', '#51452c')],
                  foreground=[('disabled', '#77796d'), ('active', '#fff0cb')])
        window.bind('<Configure>', self.schedule, add='+')
        window.bind('<Map>', self.schedule, add='+')
        window.bind('<Destroy>', self.destroyed, add='+')
        self.schedule()

    def schedule(self, event=None):
        if self.job is None:
            self.job = self.window.after_idle(self.render)

    def destroyed(self, event):
        if event.widget is self.window and self.job is not None:
            self.window.after_cancel(self.job)
            self.job = None

    def render(self):
        self.job = None
        size = self.window.winfo_width(), self.window.winfo_height()
        if size != self.size:
            self.size = size
            image = panel_image(*size)
            self.background = image
            self.canvas.delete('all')
            if image is not None:
                from PIL import ImageTk
                self.photo = ImageTk.PhotoImage(image, master=self.window)
                self.canvas.create_image(0, 0, image=self.photo, anchor='nw')
            else:
                self.canvas.create_rectangle(2, 2, size[0]-3, size[1]-3, outline=GOLD, width=2)
        self.style_children(self.window)
        self.surfaces = {w: surface for w, surface in self.surfaces.items() if w.winfo_exists()}
        for surface in self.surfaces.values():
            surface.paint()

    def style_children(self, parent):
        for child in parent.winfo_children():
            if isinstance(child, tk.Toplevel) or getattr(child, '_window_decoration', False):
                continue
            if getattr(child, '_owns_texture', False):
                continue
            if child not in self.seen:
                self.seen.add(child)
                if isinstance(child, ttk.Button) and not child.cget('style'):
                    child.configure(style='Survival.TButton')
                elif isinstance(child, tk.Button):
                    child.configure(bg='#322e20', fg=TEXT, activebackground='#51452c',
                                    activeforeground='#fff0cb', relief='flat',
                                    highlightthickness=1, highlightbackground='#8a7045')
                elif isinstance(child, (tk.Frame, tk.Label, tk.Canvas, tk.Text)):
                    if str(child.cget('bg')) in ('#202b27', '#141c1a', '#17221d'):
                        child.configure(bg=BG)
                if self.background is not None and isinstance(child, (tk.Frame, ttk.Frame, tk.Label, ttk.Label, tk.Canvas)):
                    from ui.textured_surfaces import Surface
                    self.surfaces[child] = Surface(self, child)
                elif self.background is not None and isinstance(child, tk.Text) and child.cget('state') == 'disabled':
                    from ui.textured_surfaces import TextSurface
                    self.surfaces[child] = TextSurface(self, child)
            surface = self.surfaces.get(child)
            if surface is not None and not surface.canvas.winfo_exists():
                from ui.textured_surfaces import Surface
                self.surfaces[child] = Surface(self, child)
            self.style_children(child)
        # Do not keep destroyed widgets alive across event-window transitions.
        self.seen = {widget for widget in self.seen if widget.winfo_exists()}


def apply(window, compact=False):
    if not hasattr(window, '_game_skin'):
        window._game_skin = WindowSkin(window, compact)
    return window


def clear_content(window):
    for child in window.winfo_children():
        if not getattr(child, '_window_decoration', False):
            child.destroy()
