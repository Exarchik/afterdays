"""Physics and polygon geometry adapted from the supplied zvalyshche2.py.
No standalone app or separate save file: all state lives inside the Afterdays quest.
"""
import math,random,hashlib
from dataclasses import dataclass
WIDTH,HEIGHT=850,560
MATERIALS = [('Картон', 0.4, 145, 95, '#a58d64'),
             ('Газети', 0.2, 120, 82, '#a9aaa0'),
             ('Дошка', 3.0, 205, 65, '#806044'),
             ('Мішок', 7.0, 135, 105, '#647463'),
             ('Лист металу', 16.0, 175, 112, '#6a7c7d'),
             ('Бетонна плита', 28.0, 170, 125, '#82827b')]

def inside_polygon(x, y, points):
    inside = False
    j = len(points) - 1
    for i, (xi, yi) in enumerate(points):
        xj, yj = points[j]
        if (yi > y) != (yj > y) and x < (xj-xi)*(y-yi)/(yj-yi)+xi:
            inside = not inside
        j = i
    return inside

@dataclass
class Scrap:
    number: int
    name: str
    mass: float
    x: float
    y: float
    home_x: float
    home_y: float
    points: list
    color: str

    @property
    def tag(self):
        """Повертає унікальний Canvas-тег фрагмента сміття."""
        return f'scrap{self.number}'

    def covers(self, x, y):
        """Перевіряє, чи лежить точка всередині контуру фрагмента сміття."""
        return inside_polygon(x-self.x, y-self.y, self.points)

    def step(self, dt, destination=None):
        """Важкі фрагменти повільніше слідують за рукою; усі повертаються додому."""
        if destination is not None:
            tx, ty = destination
            dx, dy = tx-self.x, ty-self.y
            distance = math.hypot(dx, dy)
            speed = 950 / (1 + self.mass * 0.20)
            fraction = min(1 - math.exp(-dt * 16 / (1+self.mass*0.06)),
                           speed*dt/distance if distance else 1)
        else:
            dx, dy = self.home_x-self.x, self.home_y-self.y
            # Півперіод повернення приблизно 4–8 секунд.
            fraction = 1 - math.exp(-dt / (5.5 + self.mass*0.20))
        move_x, move_y = dx*fraction, dy*fraction
        self.x += move_x
        self.y += move_y
        return move_x, move_y

def make_site(seed):
    rng = random.Random(seed)
    targets = []
    for row in range(2):
        for col in range(3):
            targets.append((155+col*260+rng.randint(-28,28),
                            155+row*230+rng.randint(-28,28)))
    scraps = []
    def add(x, y, kind):
        name, mass, w, h, color = MATERIALS[kind]
        angle = rng.uniform(-0.6,0.6)
        points = []
        for px, py in [(-w/2+8,-h/2),(w/2-12,-h/2+4),(w/2,h/2-12),
                       (w/2-16,h/2),(-w/2,h/2-8)]:
            points.append((px*math.cos(angle)-py*math.sin(angle),
                           px*math.sin(angle)+py*math.cos(angle)))
        scraps.append(Scrap(len(scraps),name,mass,x,y,x,y,points,color))
    # Кожна знахідка гарантовано захована під двома фрагментами.
    for x,y in targets:
        add(x,y,rng.choice([2,4,5]))
        add(x+rng.randint(-15,15),y+rng.randint(-10,10),rng.choice([0,1,3]))
    for _ in range(14):
        add(rng.randint(105,WIDTH-105),rng.randint(100,HEIGHT-100),rng.randrange(len(MATERIALS)))
    return targets, scraps

def ensure(q):
    if q.get('junk_physics')==1:return
    seed=int.from_bytes(hashlib.sha256(q['id'].encode()).digest()[:4],'big')
    targets,scraps=make_site(seed)
    loot=[obj for obj in q['junk_objects'] if obj['kind']!='debris']
    for n,obj in enumerate(loot):
        x,y=targets[n];obj.update(x=x-30,y=y-30,w=60,h=60,circle=True)
    debris=[]
    for s in scraps:
        debris.append(dict(id='debris'+str(s.number),kind='debris',found=False,material=MATERIALS.index(next(m for m in MATERIALS if m[0]==s.name)),
                           mass=s.mass,x=s.x,y=s.y,home_x=s.home_x,home_y=s.home_y,points=[list(pt) for pt in s.points],color=s.color))
    q['junk_objects']=loot+debris;q['junk_physics']=1

def covers(obj,x,y):
    if obj['kind']=='debris':return inside_polygon(x-obj['x'],y-obj['y'],obj['points'])
    return math.hypot(x-(obj['x']+30),y-(obj['y']+30))<=30

def clamp(obj,x,y):
    rx=max(abs(p[0]) for p in obj['points'])+3;ry=max(abs(p[1]) for p in obj['points'])+3
    return max(rx,min(WIDTH-rx,x)),max(ry,min(HEIGHT-ry,y))

def tick(q,dt,held=None,destination=None):
    dt=max(0,min(.05,dt));moves=[]
    for obj in q['junk_objects']:
        if obj['kind']!='debris' or obj['found']:continue
        s=Scrap(0,'',obj['mass'],obj['x'],obj['y'],obj['home_x'],obj['home_y'],obj['points'],obj['color'])
        target=clamp(obj,*destination) if obj['id']==held and destination is not None else None
        dx,dy=s.step(dt,target);obj['x'],obj['y']=s.x,s.y
        moves.append((obj['id'],dx,dy))
    return moves
