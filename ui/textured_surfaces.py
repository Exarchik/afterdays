"""Paint matching portions of a window texture behind existing Tk content.

Native labels keep their geometry and bindings; a canvas renders their visible
content. Entry/Text/Treeview controls retain their native editing surfaces.
"""
import tkinter as tk
from tkinter import ttk


class Surface:
    def __init__(self, skin, widget):
        self.skin, self.widget = skin, widget
        self.photo = None
        self.signature = None
        self.label = isinstance(widget, (tk.Label, ttk.Label))
        self.native_canvas = isinstance(widget, tk.Canvas)
        if self.native_canvas:
            self.canvas = widget
            delete, bbox = widget.delete, widget.bbox
            def protected_delete(*args):
                # A repaint of game content must not remove the texture.
                if 'all' in args:
                    ids = [i for i in widget.find_all() if '_skin_background' not in widget.gettags(i)]
                    if ids: delete(*ids)
                    args = tuple(arg for arg in args if arg != 'all')
                if args: delete(*args)
            def content_bbox(*args):
                if args == ('all',):
                    ids = [i for i in widget.find_all() if '_skin_background' not in widget.gettags(i)]
                    return bbox(*ids) if ids else None
                return bbox(*args)
            widget.delete, widget.bbox = protected_delete, content_bbox
            for option in ('xscrollcommand', 'yscrollcommand'):
                callback = widget.cget(option)
                def scrolled(first, last, callback=callback):
                    if callback: widget.tk.call(*widget.tk.splitlist(callback), first, last)
                    skin.schedule()
                widget.configure(**{option: scrolled})
        else:
            self.canvas = tk.Canvas(widget, highlightthickness=0, bd=0, takefocus=False)
            self.canvas._window_decoration = True
            self.canvas.place(x=0, y=0, relwidth=1, relheight=1, bordermode='outside')
            if self.label:
                # Preserve label click/hover bindings, including bindings added later.
                self.canvas.bindtags(widget.bindtags())
            else:
                widget.tk.call('lower', self.canvas._w)
        if self.label:
            original = widget.configure
            def configure(cnf=None, **kwargs):
                result = original(cnf, **kwargs)
                if kwargs or isinstance(cnf, dict): self.skin.schedule()
                return result
            widget.configure = widget.config = configure
            self.variable = None
            self.trace = None
            self.watch_variable()
            widget.bind('<Destroy>', self.destroyed, add='+')

    def watch_variable(self):
        name = str(self.widget.cget('textvariable'))
        if self.variable is not None and str(self.variable) == name: return
        if self.variable is not None:
            self.widget.tk.call('trace', 'remove', 'variable', self.variable, 'write', self.trace)
            self.widget.deletecommand(self.trace)
        self.variable = self.trace = None
        if name:
            self.variable = name
            self.trace = self.widget.register(lambda *args: self.skin.schedule())
            self.widget.tk.call('trace', 'add', 'variable', name, 'write', self.trace)

    def destroyed(self, event):
        if event.widget is self.widget and self.variable is not None:
            self.widget.tk.call('trace', 'remove', 'variable', self.variable, 'write', self.trace)
            self.widget.deletecommand(self.trace)
            self.variable = None

    def paint(self):
        w = self.widget
        if not w.winfo_ismapped() or self.skin.background is None: return
        if not self.canvas.winfo_exists(): return
        width, height = w.winfo_width(), w.winfo_height()
        x = w.winfo_rootx() - self.skin.window.winfo_rootx()
        y = w.winfo_rooty() - self.skin.window.winfo_rooty()
        label_options = ()
        if self.label:
            self.watch_variable()
            keys = ('text', 'font', 'foreground', 'anchor', 'justify', 'wraplength', 'image', 'compound')
            label_options = tuple(str(w.cget(key)) for key in keys)
            if self.variable is not None:
                label_options = (str(w.getvar(self.variable)),) + label_options[1:]
        signature = (self.skin.size, x, y, width, height, label_options)
        c = self.canvas
        if signature != self.signature:
            from PIL import ImageTk
            self.signature = signature
            self.photo = ImageTk.PhotoImage(self.skin.background.crop((x, y, x+width, y+height)), master=w)
            # Call base methods to avoid the content-only delete override.
            tk.Canvas.delete(c, '_skin_background')
            c.create_image(c.canvasx(0), c.canvasy(0), image=self.photo, anchor='nw', tags='_skin_background')
            c.tag_lower('_skin_background')
            if self.label: self.paint_label(label_options, width, height)
        elif self.native_canvas:
            c.coords('_skin_background', c.canvasx(0), c.canvasy(0))

    def paint_label(self, options, width, height):
        text, font, color, anchor, justify, wrap, image, compound = options
        c = self.canvas
        c.delete('_skin_label')
        anchor = anchor or 'center'
        x = 3 if anchor in ('w', 'nw', 'sw') else width-3 if anchor in ('e', 'ne', 'se') else width/2
        y = 2 if anchor in ('n', 'nw', 'ne') else height-2 if anchor in ('s', 'sw', 'se') else height/2
        # Most game labels are text-only; image labels retain their actual sprite.
        if image:
            c.create_image(x, y, image=image, anchor=anchor, tags='_skin_label')
            if compound in ('none', ''): return
        if text:
            c.create_text(x, y, text=text, font=font or 'TkDefaultFont',
                          fill=color or '#d9d3bf', anchor=anchor, justify=justify or 'left',
                          width=min(float(wrap), max(1, width-6)) if float(wrap or 0) else 0,
                          tags='_skin_label')


class TextSurface(Surface):
    """Keep native read-only text layout/selection/scrolling, paint over its fill."""
    def __init__(self, skin, widget):
        super().__init__(skin, widget)
        self.revision = 0
        for name in ('configure', 'insert', 'delete', 'tag_add', 'tag_remove', 'tag_configure'):
            original = getattr(widget, name)
            def changed(*args, _original=original, **kwargs):
                result = _original(*args, **kwargs)
                self.revision += 1
                skin.schedule()
                return result
            setattr(widget, name, changed)
        widget.config = widget.configure
        callback = widget.cget('yscrollcommand')
        def scrolled(first, last):
            if callback: widget.tk.call(*widget.tk.splitlist(callback), first, last)
            self.revision += 1
            skin.schedule()
        widget.configure(yscrollcommand=scrolled)
        # Send input to the real Text so copy, selection and mouse wheel still work.
        for sequence in ('<Button-1>', '<B1-Motion>', '<ButtonRelease-1>', '<Double-Button-1>',
                         '<MouseWheel>', '<Button-4>', '<Button-5>'):
            if sequence == '<Double-Button-1>': continue  # Tk derives doubles from clicks.
            def forward(event, seq=sequence):
                options = dict(x=event.x, y=event.y, state=event.state)
                if seq == '<MouseWheel>': options['delta'] = event.delta
                widget.event_generate(seq, **options)
                self.revision += 1;skin.schedule()
                return 'break'
            self.canvas.bind(sequence, forward)
        widget.tk.call('raise', self.canvas._w)
        self.text_signature = None

    def paint(self):
        super().paint()
        w, c = self.widget, self.canvas
        if not w.winfo_ismapped() or self.skin.background is None: return
        signature = (self.signature, self.revision, w.yview())
        if signature == self.text_signature: return
        self.text_signature = signature
        c.delete('_skin_text')
        start, end = w.index('@0,0'), w.index(f'@{w.winfo_width()},{w.winfo_height()} +1c')
        index = start
        while w.compare(index, '<', end):
            box = w.bbox(index)
            char = w.get(index)
            if box and char not in ('\n', '\t'):
                x, y, width, height = box
                font, color = w.cget('font'), w.cget('fg')
                selected = False
                for tag in w.tag_names(index):
                    font = w.tag_cget(tag, 'font') or font
                    color = w.tag_cget(tag, 'foreground') or color
                    selected |= tag == 'sel'
                if selected:
                    c.create_rectangle(x, y, x+width, y+height, fill=w.cget('selectbackground'),
                                       outline='', tags='_skin_text')
                    color = w.cget('selectforeground') or color
                c.create_text(x-1, y, text=char, font=font, fill=color, anchor='nw', tags='_skin_text')
            index = w.index(index+' +1c')
