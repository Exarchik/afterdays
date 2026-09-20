"""Vector finds adapted from the supplied minigame."""
BG,TEXT="#17201e","#eee9d9"
def target_icon(canvas, x, y, kind, color):
    """Невеликі векторні іконки, які не потребують PNG або emoji."""
    if kind == 'ammo':
        for dx in (-12,0,12):
            canvas.create_rectangle(x+dx-4,y-9,x+dx+4,y+20,fill=color,outline=TEXT)
            canvas.create_polygon(x+dx-4,y-9,x+dx,y-20,x+dx+4,y-9,fill=color,outline=TEXT)
    elif kind == 'bottle':
        canvas.create_polygon(x-6,y-21,x+6,y-21,x+6,y-10,x+12,y-4,
                              x+12,y+21,x-12,y+21,x-12,y-4,x-6,y-10,
                              fill=color, outline=TEXT, width=2)
        canvas.create_rectangle(x-9,y+1,x+9,y+11,fill='#ecdfbc',outline='')
    elif kind in ('clock', 'ring', 'wire'):
        canvas.create_oval(x-18,y-18,x+18,y+18,outline=color,width=5)
        if kind == 'clock':
            canvas.create_line(x,y-12,x,y,x+9,y+5,fill=color,width=3)
            canvas.create_rectangle(x-4,y-24,x+4,y-19,fill=color,outline='')
        elif kind == 'ring':
            canvas.create_polygon(x,y-28,x+8,y-21,x,y-14,x-8,y-21,fill=TEXT)
        else:
            canvas.create_oval(x-11,y-11,x+11,y+11,outline=color,width=3)
            canvas.create_line(x+16,y+8,x+24,y+18,fill=color,width=3)
    elif kind == 'camera':
        canvas.create_rectangle(x-24,y-15,x+24,y+18,fill=color,outline=TEXT,width=2)
        canvas.create_rectangle(x-17,y-22,x-3,y-15,fill=color,outline='')
        canvas.create_oval(x-11,y-11,x+13,y+13,fill=BG,outline=TEXT,width=2)
    elif kind == 'robot':
        canvas.create_line(x,y-26,x,y-18,fill=color,width=3)
        canvas.create_rectangle(x-15,y-18,x+15,y+3,fill=color,outline=TEXT)
        canvas.create_rectangle(x-11,y+6,x+11,y+21,fill=color,outline=TEXT)
        for dx in (-7,7):
            canvas.create_oval(x+dx-2,y-11,x+dx+2,y-7,fill=BG)
            canvas.create_line(x+dx,y+21,x+dx,y+27,fill=color,width=4)
    elif kind == 'chip':
        for d in (-12,0,12):
            canvas.create_line(x-25,y+d,x+25,y+d,fill=TEXT,width=2)
            canvas.create_line(x+d,y-25,x+d,y+25,fill=TEXT,width=2)
        canvas.create_rectangle(x-18,y-18,x+18,y+18,fill=color,outline=TEXT)
        canvas.create_rectangle(x-9,y-9,x+9,y+9,fill=BG,outline='')
    else:
        canvas.create_polygon(x-24,y-11,x+16,y-22,x+23,y-8,x-17,y+5,
                              fill=color,outline=TEXT)
        canvas.create_polygon(x-18,y+7,x+18,y-3,x+23,y+12,x-13,y+23,
                              fill=color,outline=TEXT)
