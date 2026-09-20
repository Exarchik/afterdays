"""Material drawings adapted from the supplied minigame, without weight labels."""
GOLD="#eac56d"
class ScrapArt:
    def draw_scrap(self,s):
        c = self.canvas
        points = [v for px,py in s.points for v in (s.x+px,s.y+py)]
        c.create_polygon(points,fill=s.color,outline='#222a23',width=2,tags=(s.tag,'body'+s.tag))
        # Декор цілком усередині непрозорої області.
        if s.name in ('Картон','Газети'):
            for dy in (-16,-6,4,14):
                c.create_line(s.x-30,s.y+dy,s.x+28,s.y+dy+2,fill='#777765',width=2,tags=s.tag)
        elif s.name == 'Лист металу':
            for dx in (-35,0,35):
                c.create_line(s.x+dx,s.y-23,s.x+dx+4,s.y+20,fill='#899796',width=3,tags=s.tag)
        elif s.name == 'Бетонна плита':
            c.create_line(s.x-22,s.y-28,s.x-4,s.y-9,s.x-12,s.y+5,
                          s.x+18,s.y+24,fill='#565952',width=3,tags=s.tag)
        elif s.name == 'Дошка':
            c.create_line(s.x-45,s.y-8,s.x+45,s.y+9,fill='#a17e55',width=2,tags=s.tag)
        else:
            c.create_line(s.x-25,s.y-16,s.x+10,s.y+18,s.x+30,s.y-12,
                          fill='#89927d',width=2,tags=s.tag)
