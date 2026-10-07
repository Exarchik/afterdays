"""Display-independent retained canvas commands and triangle tessellation."""
from dataclasses import dataclass, field
import math


def flatten(values):
    out = []
    for value in values:
        if isinstance(value, (list, tuple)):
            out.extend(flatten(value))
        else:
            out.append(float(value))
    return tuple(out)


@dataclass
class Command:
    kind: str
    points: tuple
    options: dict = field(default_factory=dict)

    @property
    def tags(self):
        tags = self.options.get('tags', ())
        return (tags,) if isinstance(tags, str) else tuple(tags)

    def key(self):
        def freeze(v):
            return tuple(freeze(x) for x in v) if isinstance(v, (tuple, list)) else v
        return self.kind, self.points, tuple(sorted((k, freeze(v)) for k, v in self.options.items() if k not in ('tags', 'image')))


class Scene:
    def __init__(self):
        self.items = {}
        self.serial = 0
        self.revision = 0

    def add(self, kind, points, options):
        self.serial += 1
        self.items[self.serial] = Command(kind, flatten(points), dict(options))
        self.revision += 1
        return self.serial

    def ids(self, selector):
        if isinstance(selector, int):
            return (selector,) if selector in self.items else ()
        return tuple(i for i, c in self.items.items() if selector == 'all' or selector in c.tags)

    def delete(self, *selectors):
        ids = {i for selector in selectors for i in self.ids(selector)}
        if ids:
            for i in ids:
                del self.items[i]
            self.revision += 1

    def coords(self, selector, *points):
        ids = self.ids(selector)
        if points:
            for i in ids:
                self.items[i].points = flatten(points)
            if ids:
                self.revision += 1
        return list(self.items[ids[0]].points) if ids else []

    def move(self, selector, dx, dy):
        ids = self.ids(selector)
        for i in ids:
            c = self.items[i]
            c.points = tuple(v + (dx if n % 2 == 0 else dy) for n, v in enumerate(c.points))
        if ids:
            self.revision += 1

    def configure(self, selector, **options):
        ids = self.ids(selector)
        for i in ids:
            self.items[i].options.update(options)
        if ids:
            self.revision += 1

    def reorder(self, selector, relative=None, above=True):
        selected = self.ids(selector)
        order = [i for i in self.items if i not in selected]
        targets = [i for i in self.ids(relative) if i in order] if relative is not None else []
        at = (order.index(targets[-1]) + 1 if above else order.index(targets[0])) if targets else (len(order) if above else 0)
        order[at:at] = selected
        self.items = {i: self.items[i] for i in order}
        self.revision += 1


def triangles(points):
    """Ear clipping, including concave player arrows; preserve paint order."""
    pts = list(points)
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts.pop()
    if len(pts) < 3:
        return []
    cross = lambda a, b, c: (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    area = sum(a[0]*b[1]-b[0]*a[1] for a, b in zip(pts, pts[1:]+pts[:1]))
    if area < 0:
        pts.reverse()
    out = []
    while len(pts) > 3:
        for i, b in enumerate(pts):
            a, c = pts[i-1], pts[(i+1) % len(pts)]
            if cross(a, b, c) <= 1e-9:
                continue
            if any(cross(a,b,p) >= 0 and cross(b,c,p) >= 0 and cross(c,a,p) >= 0 for p in pts if p not in (a,b,c)):
                continue
            out.extend((a,b,c))
            pts.pop(i)
            break
        else:
            # Degenerate/collinear vertices contribute no area.
            for i in range(1, len(pts)-1):
                out.extend((pts[0],pts[i],pts[i+1]))
            return out
    return out + pts


def stroke(points, width=1, dash=()):
    out = []
    pattern = tuple(max(.1,float(v)) for v in dash)
    if len(pattern) % 2:
        pattern *= 2
    phase = 0
    remaining = pattern[0] if pattern else float('inf')
    for a, b in zip(points, points[1:]):
        dx, dy = b[0]-a[0], b[1]-a[1]
        length = math.hypot(dx,dy)
        if length < 1e-9:
            continue
        nx, ny = -dy/length*width/2, dx/length*width/2
        distance = 0
        while distance < length-1e-9:
            step = min(remaining, length-distance)
            if phase % 2 == 0:
                p = (a[0]+dx*distance/length,a[1]+dy*distance/length)
                q = (a[0]+dx*(distance+step)/length,a[1]+dy*(distance+step)/length)
                aa,bb,cc,dd = (p[0]+nx,p[1]+ny),(q[0]+nx,q[1]+ny),(q[0]-nx,q[1]-ny),(p[0]-nx,p[1]-ny)
                out.extend((aa,bb,cc,aa,cc,dd))
            distance += step
            remaining -= step
            if remaining < 1e-9 and pattern:
                phase = (phase+1) % len(pattern)
                remaining = pattern[phase]
    return out


def geometry(command):
    """Return ordered (triangle vertices, color) runs in top-left coordinates."""
    kind, p, o = command.kind, command.points, command.options
    points = list(zip(p[::2],p[1::2]))
    fill = o.get('fill', 'black' if kind in ('polygon','line') else '')
    outline = o.get('outline', 'black' if kind in ('rectangle','oval') else '')
    if kind == 'rectangle':
        x1,y1,x2,y2 = p
        points = [(x1,y1),(x2,y1),(x2,y2),(x1,y2)]
    elif kind == 'oval':
        x1,y1,x2,y2 = p
        cx,cy,rx,ry = (x1+x2)/2,(y1+y2)/2,abs(x2-x1)/2,abs(y2-y1)/2
        n = max(16,min(96,int(max(rx,ry)*1.5)))
        points = [(cx+rx*math.cos(i*math.tau/n),cy+ry*math.sin(i*math.tau/n)) for i in range(n)]
    out = []
    if kind == 'line':
        if fill:
            out.append((stroke(points,float(o.get('width',1)),o.get('dash',())),fill))
    else:
        if fill:
            out.append((triangles(points),fill))
        if outline and points:
            out.append((stroke(points+points[:1],float(o.get('width',1)),o.get('dash',())),outline))
    return out
