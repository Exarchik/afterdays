"""Top-down drawing of junkyard pile pieces: material colour, outline and surface marks."""
import math
import junk_physics as pile

MARKS={'Лист металу':'#8a9a99','Бетонна плита':'#5f625a','Дошка':'#a17e55','Мішок':'#7d8b78'}


def local(piece,x,y):
    c,s=math.cos(piece['a']),math.sin(piece['a'])
    return piece['x']+x*c-y*s,piece['y']+x*s+y*c


def draw_piece(canvas,piece,outline=None):
    """Draws one piece in model coordinates; marks stay inside the piece outline."""
    name,_,w,h,colour=pile.MATERIALS[piece['material']]
    points=[v for pt in pile.corners(piece) for v in pt]
    canvas.create_polygon(*[v+3 for v in points],fill='#20261d',outline='')
    canvas.create_polygon(*points,fill=colour,outline=outline or '#1b221d',width=3 if outline else 1)
    mark=MARKS.get(name,'#78786a');hw,hh=w/2,h/2
    if name in ('Газети','Картон'):
        lines=[((-hw+14,y),(hw-14,y+2)) for y in (-18,-7,4,15) if abs(y)<hh-6]
    elif name=='Лист металу':
        lines=[((x,-hh+4),(x,hh-4)) for x in (-50,-15,20,55)]
    elif name=='Бетонна плита':
        lines=[((-40,-50),(-10,-12)),((-10,-12),(-22,10)),((-22,10),(30,48))]
    elif name=='Дошка':
        lines=[((-hw+4,-9),(hw-4,-6)),((-hw+4,4),(hw-4,7))]
    else:
        lines=[((-30,-20),(10,22)),((10,22),(35,-14))]
    for a,b in lines:
        canvas.create_line(*local(piece,*a),*local(piece,*b),fill=mark,width=3 if name in ('Лист металу','Бетонна плита') else 2)
