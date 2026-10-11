"""Show vertical scrollbars only while their content overflows."""


def auto_scrollbar(view, bar, *, grid=False):
    """Connect an already placed scrollbar, preserving its layout when hidden."""
    visible = True
    def update(first, last):
        nonlocal visible
        bar.set(first, last)
        needed = float(last) - float(first) < .999999
        if needed == visible:
            return
        visible = needed
        if grid:
            if needed:bar.grid()
            else:bar.grid_remove()
        elif needed:
            bar.pack(side='right', fill='y', before=view)
        else:
            bar.pack_forget()
    view.configure(yscrollcommand=update)
