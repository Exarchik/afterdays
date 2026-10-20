"""Flight and impact of one shot on the arena canvas, by damage type.

Everything is plain Tk items (lines, ovals, polygons) tagged 'fx'; semi-transparent
effects use stipple. `t` runs 0..1 over the attack event; the projectile arrives at
ARRIVE[type] and the rest of the event is the impact.
"""
import math
import random

ARRIVE={'kinetic':.5,'piercing':.32,'thermal':.72,'energy':.55,'electric':.4}
MUZZLE={'kinetic':'#ffe08a','piercing':'#f4ffe0','thermal':'#ff9a50','energy':'#bff7f1','electric':'#e2d2ff'}


def zigzag(x1,y1,x2,y2,amp,rng):
    length=math.hypot(x2-x1,y2-y1) or 1;n=max(3,round(length/10))
    nx,ny=-(y2-y1)/length,(x2-x1)/length;points=[x1,y1]
    for i in range(1,n):
        k=i/n;j=rng.uniform(-amp,amp);points+=[x1+(x2-x1)*k+nx*j,y1+(y2-y1)*k+ny*j]
    return points+[x2,y2]


def draw(c,e,sx,sy,px,py,t,u=14):
    """Draw one projectile event; returns nothing. Unknown types fall back to kinetic."""
    kind=e.get('damage_type','kinetic')
    if kind not in ARRIVE:kind='kinetic'
    small=e.get('fire_mode')=='pellet'
    s=max(.6,min(1.5,u/14))*(.7 if small else 1)
    seed=hash((e.get('volley'),e.get('projectile',0)))&0xffff
    arrive=ARRIVE[kind];length=math.hypot(px-sx,py-sy) or 1;dx,dy=(px-sx)/length,(py-sy)/length
    if t<arrive:
        k=t/arrive;hx,hy=sx+(px-sx)*k,sy+(py-sy)*k
        def back(n):
            n=min(n,length*k);return hx-dx*n,hy-dy*n
        if t<.1:
            r=(1-t/.1)*11*s;points=[]
            for i in range(8):
                a=i*math.pi/4;rr=r if i%2==0 else r*.38
                points+=[sx+math.cos(a)*rr,sy+math.sin(a)*rr]
            c.create_polygon(*points,fill=MUZZLE[kind],outline='',tags='fx')
        if kind=='kinetic':
            bx,by=back(26*s)
            c.create_line(bx,by,hx,hy,fill='#a8803c',width=max(1,3*s),tags='fx')
            c.create_line(bx+dx*8,by+dy*8,hx,hy,fill='#ffe3a0',width=max(1,1.6*s),tags='fx')
            c.create_oval(hx-2*s,hy-2*s,hx+2*s,hy+2*s,fill='#fff6d8',outline='',tags='fx')
        elif kind=='piercing':
            bx,by=back(64*s)
            c.create_line(bx,by,hx,hy,fill='#9fae8a',width=1,tags='fx')
            c.create_line(bx+dx*30*s,by+dy*30*s,hx,hy,fill='#f4ffe0',width=max(1,1.5*s),tags='fx')
            c.create_rectangle(hx-1.5,hy-1.5,hx+1.5,hy+1.5,fill='#ffffff',outline='',tags='fx')
        elif kind=='thermal':
            rng=random.Random(seed)
            for i in range(7):
                back_k=rng.uniform(.04,.5);ex,ey=hx-dx*length*k*back_k+rng.uniform(-3,3),hy-dy*length*k*back_k+rng.uniform(-3,3)-back_k*6
                color='#ffcf70' if back_k<.15 else '#ff7a3a' if back_k<.32 else '#7a2a14'
                c.create_rectangle(ex-1.2,ey-1.2,ex+1.2,ey+1.2,fill=color,outline='',tags='fx')
            for r,color in ((6.5,'#b8401c'),(4.6,'#ff9160'),(2.4,'#ffe28a')):
                r*=s;c.create_oval(hx-r,hy-r,hx+r,hy+r,fill=color,outline='',tags='fx')
        elif kind=='energy':
            bx,by=back(22*s)
            for width,color in ((8,'#2f8f86'),(5,'#88e3d9'),(2,'#f2fffd')):
                c.create_line(bx,by,hx,hy,fill=color,width=max(1,width*s),capstyle='round',tags='fx')
        else:
            bx,by=back(70*s);rng=random.Random(seed*7+int(t*25))
            points=zigzag(bx,by,hx,hy,5*s,rng)
            for width,color in ((4,'#5d3fa0'),(2.2,'#bf9dff'),(1,'#f5eeff')):
                c.create_line(*points,fill=color,width=max(1,width*s),joinstyle='round',tags='fx')
        return
    k=(t-arrive)/max(.01,1-arrive);hit=e.get('hit',True);wall=e.get('wall',False)
    rng=random.Random(seed)
    if kind=='kinetic':
        color='#cfcabb' if wall or not hit else '#8d7f63'
        for _ in range(3 if small else 6):
            vx,vy=rng.uniform(-1,1)*14*s,rng.uniform(-1,.3)*12*s;r=(2+3*k)*s
            x,y=px+vx*k,py+vy*k;c.create_oval(x-r,y-r,x+r,y+r,fill=color,outline='',stipple='gray50' if k>.5 else '',tags='fx')
    elif kind=='piercing':
        for _ in range(4 if small else 8):
            a=rng.uniform(0,2*math.pi);d=(6+20*k)*s
            x,y=px+math.cos(a)*d,py+math.sin(a)*d
            c.create_line(x,y,x-math.cos(a)*6*s,y-math.sin(a)*6*s,fill='#f4ffd8',width=1,tags='fx')
        r=(4+16*k)*s;c.create_oval(px-r,py-r*.6,px+r,py+r*.6,outline='#e6f2cf',width=1,tags='fx')
    elif kind=='thermal':
        r=(8 if small else 12)*s;c.create_oval(px-r*1.4,py-r*.5,px+r*1.4,py+r*.7,fill='#1c140e',outline='',stipple='gray50',tags='fx')
        for i in range(5):
            a=-math.pi/2+(i-2)*.45;h=(10+8*math.sin(k*25+i*2))*s*(1-k*.8)
            c.create_polygon(px+math.cos(a-.25)*4*s,py+math.sin(a-.25)*4*s,px+math.cos(a)*h,py+math.sin(a)*h,
                             px+math.cos(a+.25)*4*s,py+math.sin(a+.25)*4*s,fill='#ff7a3a' if i%2 else '#ffc35a',outline='',tags='fx')
    elif kind=='energy':
        r=(4+(16 if small else 26)*k)*s;c.create_oval(px-r,py-r*.65,px+r,py+r*.65,outline='#88e3d9',width=max(1,3*(1-k)+.5),tags='fx')
        if k<.3:
            f=(10 if not small else 6)*s*(1-k/.3);c.create_oval(px-f,py-f,px+f,py+f,fill='#ffffff',outline='',tags='fx')
    else:
        jitter=random.Random(seed*13+int(t*20))
        for _ in range(2 if small else 4):
            a=jitter.uniform(0,2*math.pi);L=jitter.uniform(14,28)*s
            points=zigzag(px,py,px+math.cos(a)*L,py+math.sin(a)*L,4*s,jitter)
            c.create_line(*points,fill='#7b5cc8',width=max(1,2.4*s),tags='fx')
            c.create_line(*points,fill='#e9ddff',width=1,tags='fx')
