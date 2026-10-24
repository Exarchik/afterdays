"""Flight and impact of one shot on the arena canvas, by damage type.

Everything is plain Tk items (lines, ovals, polygons) tagged 'fx'; semi-transparent
effects use stipple. `t` runs 0..1 over the attack event; the projectile arrives at
ARRIVE[type] and the rest of the event is the impact.
"""
import math
import random

ARRIVE={'kinetic':.5,'piercing':.32,'thermal':.72,'energy':.55,'electric':.4}
# Weapon looks chosen in the editor (equipment 'projectile'); events carry them as 'look'.
LOOKS={'laser_bolt':.3,'railgun':.14,'plasma_red':.26,'heavy':.42,'laser_beam':.06,'red_beam':.03}
# A railgun's trail lingers, so its event lasts longer (seconds).
DURATION={'railgun':.8,'laser_beam':.6,'red_beam':1.0}
# Monster and melee styles (see game/systems/attack_looks.py).
STYLE_ARRIVE={'spit':.62,'acid':.6,'laser':.28,'mud':.6,'web':.45,'bite':.45,'claw':.4,'smash':.5,'punch':.4}
MUZZLE={'kinetic':'#ffe08a','piercing':'#f4ffe0','thermal':'#ff9a50','energy':'#bff7f1','electric':'#e2d2ff',
        'laser_bolt':'#fff2a0','railgun':'#d8f4ff','plasma_red':'#ffb09a','heavy':'#fff0b0','laser_beam':'#fff1b0','red_beam':'#ffb0a8'}


def zigzag(x1,y1,x2,y2,amp,rng):
    length=math.hypot(x2-x1,y2-y1) or 1;n=max(3,round(length/10))
    nx,ny=-(y2-y1)/length,(x2-x1)/length;points=[x1,y1]
    for i in range(1,n):
        k=i/n;j=rng.uniform(-amp,amp);points+=[x1+(x2-x1)*k+nx*j,y1+(y2-y1)*k+ny*j]
    return points+[x2,y2]


def look(e):
    """Animation of a shot: the weapon's own look if set, else its damage type."""
    if e.get('look') in LOOKS or e.get('look') in ARRIVE:return e['look']
    return e.get('damage_type','kinetic') if e.get('damage_type') in ARRIVE else 'kinetic'


def arrive(e):
    """Fraction of the event at which the blow lands."""
    style=e.get('attack_style')
    if style in STYLE_ARRIVE:return STYLE_ARRIVE[style]
    kind=look(e)
    return LOOKS.get(kind,ARRIVE.get(kind,.5))


def duration(e,default):
    """Event length in seconds; some looks need longer than a plain shot."""
    return max(default,DURATION.get(e.get('look'),0))


def draw(c,e,sx,sy,px,py,t,u=14):
    """Draw one projectile event; returns nothing. Unknown types fall back to kinetic."""
    if e.get('attack_style') in STYLE_ARRIVE:return draw_style(c,e,sx,sy,px,py,t,u)
    kind=look(e)
    small=e.get('fire_mode')=='pellet'
    s=max(.6,min(1.5,u/14))*(.7 if small else 1)
    seed=hash((e.get('volley'),e.get('projectile',0)))&0xffff
    if kind in LOOKS:return _draw_look(c,e,kind,sx,sy,px,py,t,s,small,seed)
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


def _flash(c,x,y,r,color):
    points=[]
    for i in range(8):
        a=i*math.pi/4+.2;rr=r if i%2==0 else r*.38
        points+=[x+math.cos(a)*rr,y+math.sin(a)*rr]
    c.create_polygon(*points,fill=color,outline='',tags='fx')


def _ellipse(cx,cy,a,b,dx,dy,n=14):
    """Polygon points of an ellipse with its long axis along (dx,dy)."""
    points=[]
    for i in range(n):
        q=i/n*2*math.pi;u,v=math.cos(q)*a,math.sin(q)*b
        points+=[cx+u*dx-v*dy,cy+u*dy+v*dx]
    return points


def _helix(sx,sy,px,py,radius,turn,phase):
    """Spiral around the line sx,sy→px,py: (front, back) runs of points, front faces the viewer."""
    length=math.hypot(px-sx,py-sy) or 1;dx,dy=(px-sx)/length,(py-sy)/length;nx,ny=-dy,dx
    n=max(8,int(length/1.5));runs=([],[]);current=None;run=[]
    for i in range(n+1):
        d=length*i/n;a=d/turn*2*math.pi+phase;off=math.sin(a)*radius
        x,y=sx+dx*d+nx*off,sy+dy*d+ny*off;front=math.cos(a)>=0
        if front!=current and run:
            run+=[x,y];runs[0 if current else 1].append(run);run=[]
        current=front;run+=[x,y]
    if len(run)>=4:runs[0 if current else 1].append(run)
    return runs


def _draw_look(c,e,kind,sx,sy,px,py,t,s,small,seed):
    """The four editor looks: yellow laser bolt, railgun spiral, red plasma, heavy round."""
    arrive=LOOKS[kind];length=math.hypot(px-sx,py-sy) or 1;dx,dy=(px-sx)/length,(py-sy)/length
    hit=e.get('hit',True);wall=e.get('wall',False);rng=random.Random(seed)
    if kind=='red_beam':
        # Thin red beam hits at once; after half a second the wind blows it apart into sparks.
        BREAK=.2;length_px=math.hypot(px-sx,py-sy) or 1;nx,ny=-(py-sy)/length_px,(px-sx)/length_px
        if t<BREAK:
            flicker=1+.15*math.sin(t*110+seed)
            for width,color in ((4,'#6e0a0a'),(2,'#e0201a'),(.9,'#ffd0c8')):
                c.create_line(sx,sy,px,py,fill=color,width=max(1,width*s*flicker),tags='fx')
            r=(3.2+1.2*math.sin(t*80))*s
            c.create_oval(px-r,py-r,px+r,py+r,fill='#ff4a3a',outline='',tags='fx')
            c.create_oval(sx-2.4*s,sy-2.4*s,sx+2.4*s,sy+2.4*s,fill='#ff8a7a',outline='',tags='fx')
            return
        k=(t-BREAK)/(1-BREAK);wind=random.Random(seed*17)
        gust=(.9,-.35)  # the same wind for every spark: drifting right and up
        n=max(12,int(length_px/5))
        for i in range(n):
            f=(i+wind.random())/n;x0,y0=sx+(px-sx)*f,sy+(py-sy)*f
            delay=wind.uniform(0,.35)  # sparks peel off one by one, not all at once
            q=max(0,(k-delay)/(1-delay))
            if q<=0:
                c.create_line(x0,y0,x0+(px-sx)/n,y0+(py-sy)/n,fill='#e0201a',width=max(1,1.6*s),tags='fx');continue
            if q>=1:continue
            speed=wind.uniform(18,46)*s;swirl=wind.uniform(-1,1)*8*s
            x=x0+gust[0]*speed*q+nx*swirl*math.sin(q*6+i);y=y0+gust[1]*speed*q+ny*swirl*math.sin(q*6+i)-10*s*q*q
            size=max(.6,(1.6-1.2*q)*s)
            color='#ff5a40' if q<.3 else '#ff9a5a' if q<.6 else '#a04030'
            c.create_rectangle(x-size,y-size,x+size,y+size,fill=color,outline='',stipple='gray50' if q>.65 else '',tags='fx')
        return
    if kind=='laser_beam':
        # Instant beam over the whole line: holds, flickers a little, then thins out and fades.
        fade=max(0,(t-.55)/.45);flicker=1+.12*math.sin(t*90+seed)
        widths=((4.5,'#9a3a06'),(2.8,'#ff7a12'),(1.5,'#ffc23a'),(0.7,'#fff6d0'))
        stipple='gray50' if fade>.5 else ''
        for width,color in widths[:4 if fade<.6 else 2]:
            c.create_line(sx,sy,px,py,fill=color,width=max(1,width*s*flicker*(1-fade*.7)),capstyle='round',stipple=stipple,tags='fx')
        g=(6+2*math.sin(t*70))*s*(1-fade*.6)
        c.create_oval(sx-g,sy-g,sx+g,sy+g,fill='#ffd36a',outline='',tags='fx')
        if t>=arrive:
            r=(7+3*math.sin(t*60))*s*(1-fade*.5)
            c.create_oval(px-r*1.6,py-r*.8,px+r*1.6,py+r*.8,fill='#ff6a10',outline='',stipple='gray50',tags='fx')
            c.create_oval(px-r*.7,py-r*.7,px+r*.7,py+r*.7,fill='#fff1b0',outline='',tags='fx')
            spark=random.Random(seed*31+int(t*30))
            for _ in range(0 if small else 5):
                a=spark.uniform(0,2*math.pi);d=spark.uniform(4,16)*s;x,y=px+math.cos(a)*d,py+math.sin(a)*d
                c.create_line(x,y,x+math.cos(a)*4*s,y+math.sin(a)*4*s,fill='#ffb23a',width=1,tags='fx')
            if fade>0:
                for i in range(3):
                    x,y=px+(i-1)*5*s,py-(6+18*fade+i*3)*s;q=(2+3*fade)*s
                    c.create_oval(x-q,y-q,x+q,y+q,fill='#5a5248',outline='',stipple='gray25',tags='fx')
        return
    if kind=='railgun':
        # The slug is near-instant; the trail stays and slowly falls apart.
        reach=min(1,t/arrive);hx,hy=sx+(px-sx)*reach,sy+(py-sy)*reach
        fade=max(0,(t-arrive)/(1-arrive))
        radius=(5+6*fade)*s;phase=fade*2.2
        front,back=_helix(sx,sy,hx,hy,radius,30*s,phase)
        step=min(3,int(fade*4))
        dim='gray50' if fade>.55 else ''
        back_color=('#2b6fae','#235d93','#1c4a75','#173c5e')[step];front_color=('#9fe2ff','#7fcff7','#5aa8d8','#3f7fb0')[step]
        for run in back:c.create_line(*run,fill=back_color,width=max(1,1.6*s),tags='fx')
        if fade<.85:
            core=('#ffffff','#d8f2ff','#9ccbe6','#7fb6d8')[step]
            c.create_line(sx,sy,hx,hy,fill=core,width=max(1,(2.6-2.2*fade)*s),stipple=dim,tags='fx')
        for run in front:c.create_line(*run,fill=front_color,width=max(1,2.8*s*(1-fade*.4)),capstyle='round',stipple=dim,tags='fx')
        if t<.12:_flash(c,sx,sy,(1-t/.12)*13*s,MUZZLE[kind])
        if t>=arrive:
            k=fade;r=(5+24*k)*s
            c.create_oval(px-r,py-r*.6,px+r,py+r*.6,outline='#9fe0ff' if k<.5 else '#3f7fb0',width=max(1,3*(1-k)+.5),tags='fx')
            if k<.25:f=12*s*(1-k/.25);c.create_oval(px-f,py-f,px+f,py+f,fill='#eaf8ff',outline='',tags='fx')
            for _ in range(0 if small else 6):
                a=rng.uniform(0,2*math.pi);d=(5+26*k)*s;x,y=px+math.cos(a)*d,py+math.sin(a)*d
                c.create_line(x,y,x-math.cos(a)*5*s,y-math.sin(a)*5*s,fill='#cfeeff',width=1,tags='fx')
        return
    if t<arrive:
        k=t/arrive;hx,hy=sx+(px-sx)*k,sy+(py-sy)*k
        def back(n):
            n=min(n,length*k);return hx-dx*n,hy-dy*n
        if t<.1:_flash(c,sx,sy,(1-t/.1)*(20 if kind=='heavy' else 11)*s,MUZZLE[kind])
        if kind=='laser_bolt':
            bx,by=back(20*s)
            for width,color in ((7,'#8a6a08'),(4,'#ffd21a'),(1.6,'#fffbe0')):
                c.create_line(bx,by,hx,hy,fill=color,width=max(1,width*s),capstyle='round',tags='fx')
        elif kind=='plasma_red':
            for i,(back_k,color) in enumerate(((.22,'#5a0a0a'),(.14,'#9a1410'),(.07,'#d8261a'))):
                x,y=back(length*back_k*k+6*s);r=(2.4-i*.4)*s
                c.create_oval(x-r,y-r,x+r,y+r,fill=color,outline='',stipple='gray50',tags='fx')
            for a,b,color in ((9,5.5,'#7a0d0d'),(6.5,4,'#ff2a1a'),(3.2,2,'#ffd6c0')):
                c.create_polygon(*_ellipse(hx,hy,a*s,b*s,dx,dy),fill=color,outline='',tags='fx')
        else:  # heavy round: thick tracer, the air ripples behind it
            bx,by=back(44*s)
            c.create_line(bx,by,hx,hy,fill='#7a5520',width=max(1,6*s),tags='fx')
            c.create_line(bx+dx*10*s,by+dy*10*s,hx,hy,fill='#ffe7a8',width=max(1,2.8*s),tags='fx')
            c.create_oval(hx-3.4*s,hy-3.4*s,hx+3.4*s,hy+3.4*s,fill='#fff8e0',outline='',tags='fx')
            if k<.5:r=(5+14*k)*s;c.create_oval(sx-r,sy-r*.7,sx+r,sy+r*.7,outline='#d8cfb8',width=1,tags='fx')
            for i in range(3):
                x,y=sx+dx*(10+i*8)*s+rng.uniform(-2,2),sy+dy*(10+i*8)*s-4*k*s;r=(4+5*k+i)*s
                c.create_oval(x-r,y-r,x+r,y+r,fill='#6b665c',outline='',stipple='gray25',tags='fx')
        return
    k=(t-arrive)/max(.01,1-arrive)
    if kind=='laser_bolt':
        if k<.35:_flash(c,px,py,9*s*(1-k/.35)+3,'#fff3a0')
        for _ in range(3 if small else 5):
            a=rng.uniform(0,2*math.pi);d=(4+16*k)*s;x,y=px+math.cos(a)*d,py+math.sin(a)*d
            c.create_line(x,y,x-math.cos(a)*5*s,y-math.sin(a)*5*s,fill='#ffe35a',width=max(1,1.4*s),tags='fx')
        r=3.5*s;c.create_oval(px-r,py-r*.6,px+r,py+r*.6,fill='#3a2a0a',outline='#ffcf30' if k<.5 else '',stipple='gray50',tags='fx')
    elif kind=='plasma_red':
        r=(5+22*k)*s;c.create_oval(px-r,py-r*.65,px+r,py+r*.65,outline='#ff3b2a',width=max(1,3*(1-k)+.5),tags='fx')
        if k<.3:
            f=11*s*(1-k/.3)
            for rr,color in ((f,'#ff3b2a'),(f*.55,'#ffd0b0')):c.create_oval(px-rr,py-rr,px+rr,py+rr,fill=color,outline='',tags='fx')
        for _ in range(4 if small else 9):
            vx,vy=rng.uniform(-1,1)*18*s,rng.uniform(-1.2,-.2)*16*s
            x,y=px+vx*k,py+vy*k+30*s*k*k;r=max(.8,1.8*s*(1-k*.6))
            c.create_oval(x-r,y-r,x+r,y+r,fill='#ff8a3a' if k<.5 else '#a02a14',outline='',tags='fx')
        c.create_oval(px-9*s,py-4*s,px+9*s,py+5*s,fill='#ff5030',outline='',stipple='gray25',tags='fx')
    else:
        color='#cfcabb' if wall or not hit else '#8d7f63'
        r=(6+34*k)*s;c.create_oval(px-r,py-r*.55,px+r,py+r*.55,outline='#e8dfc4',width=max(1,3.5*(1-k)),tags='fx')
        if k<.2:_flash(c,px,py,16*s*(1-k/.2)+4,'#fff0b0')
        for _ in range(5 if small else 11):
            vx,vy=rng.uniform(-1,1)*22*s,rng.uniform(-1,.2)*20*s;r=(3+5*k)*s
            x,y=px+vx*k,py+vy*k;c.create_oval(x-r,y-r,x+r,y+r,fill=color,outline='',stipple='gray50' if k>.45 else '',tags='fx')
        for _ in range(0 if small else 6):
            vx,vy=rng.uniform(-1,1)*30*s,rng.uniform(-1.4,-.4)*22*s
            x,y=px+vx*k,py+vy*k+40*s*k*k;q=2*s
            c.create_rectangle(x-q,y-q,x+q,y+q,fill='#3b342a',outline='',tags='fx')


def _arc_point(sx,sy,px,py,k,lift):
    """Point on a thrown arc: straight in plan, lifted by a parabola."""
    return sx+(px-sx)*k,sy+(py-sy)*k-lift*4*k*(1-k)


def draw_style(c,e,sx,sy,px,py,t,u=14):
    """Monster spit, acid, laser, mud, web and melee bites, claws, smashes and punches."""
    style=e['attack_style'];s=max(.6,min(1.5,u/14))
    seed=hash((e.get('source') and tuple(e['source']),tuple(e.get('pos') or ()),style))&0xffff
    arrive=STYLE_ARRIVE[style];length=math.hypot(px-sx,py-sy) or 1
    hit=e.get('hit',True);rng=random.Random(seed)
    if t<arrive:
        k=t/arrive
        if style in ('spit','acid','mud'):
            lift=length*(.28 if style!='acid' else .16)
            hx,hy=_arc_point(sx,sy,px,py,k,lift)
            body,edge={'spit':('#b8d84a','#55701f'),'acid':('#7fe05a','#2f7a24'),'mud':('#6b5332','#3a2c1a')}[style]
            for n in range(1,4):
                tx,ty=_arc_point(sx,sy,px,py,max(0,k-.06*n),lift);r=(3.5-n*.8)*s
                c.create_oval(tx-r,ty-r,tx+r,ty+r,fill=body,outline='',tags='fx')
            if style=='acid':
                for n in range(3):
                    dk=max(0,k-.1*(n+1));tx,ty=_arc_point(sx,sy,px,py,dk,lift);ty+=(n+1)*4*s
                    c.create_oval(tx-1.3,ty-1.3,tx+1.3,ty+1.3,fill=body,outline='',tags='fx')
            r=5.5*s;c.create_oval(hx-r,hy-r*.85,hx+r,hy+r*.85,fill=body,outline=edge,width=1,tags='fx')
            c.create_oval(hx-r*.35-1,hy-r*.5,hx-r*.35+1.5,hy-r*.5+2,fill='#f4ffd0',outline='',tags='fx')
        elif style=='laser':
            hx,hy=sx+(px-sx)*k,sy+(py-sy)*k
            c.create_line(sx,sy,hx,hy,fill='#a01e14',width=max(1,4*s),tags='fx')
            c.create_line(sx,sy,hx,hy,fill='#ff4a3a',width=max(1,2.2*s),tags='fx')
            c.create_line(sx,sy,hx,hy,fill='#ffd8d0',width=1,tags='fx')
        elif style=='web':
            hx,hy=sx+(px-sx)*k,sy+(py-sy)*k;mx,my=(sx+hx)/2,(sy+hy)/2+length*k*.05
            c.create_line(sx,sy,mx,my,hx,hy,fill='#e8e8dc',width=1,smooth=True,tags='fx')
            c.create_oval(hx-2*s,hy-2*s,hx+2*s,hy+2*s,fill='#f6f6ee',outline='',tags='fx')
        else:
            # Melee: a short lunge streak towards the target.
            a=max(0,k-.35);c.create_line(sx+(px-sx)*a,sy+(py-sy)*a,sx+(px-sx)*k*.85,sy+(py-sy)*k*.85,
                                         fill='#d9cdb2',width=max(1,2*s),dash=(3,3),tags='fx')
        return
    k=(t-arrive)/max(.01,1-arrive)
    if style in ('spit','acid','mud'):
        body={'spit':'#b8d84a','acid':'#7fe05a','mud':'#6b5332'}[style]
        r=(7+6*k)*s;c.create_oval(px-r*1.3,py-r*.45,px+r*1.3,py+r*.55,fill=body,outline='',stipple='gray50',tags='fx')
        for _ in range(6):
            a=rng.uniform(math.pi,2*math.pi);d=(4+16*k)*s
            x,y=px+math.cos(a)*d,py+math.sin(a)*d*.7+12*k*k*s;rr=max(1,2.2*s*(1-k*.5))
            c.create_oval(x-rr,y-rr,x+rr,y+rr,fill=body,outline='',tags='fx')
        if style=='acid':
            for n in range(3):
                x=px+rng.uniform(-8,8)*s;y=py-(4+14*((k+n*.3)%1))*s;rr=1.5*s
                c.create_oval(x-rr,y-rr,x+rr,y+rr,outline='#c8ffb0',width=1,tags='fx')
    elif style=='laser':
        r=(3+10*k)*s;c.create_oval(px-r,py-r*.6,px+r,py+r*.6,outline='#ff6a5a',width=2,tags='fx')
        for _ in range(5):
            a=rng.uniform(0,2*math.pi);d=(4+12*k)*s
            c.create_line(px+math.cos(a)*d,py+math.sin(a)*d,px+math.cos(a)*(d+4*s),py+math.sin(a)*(d+4*s),fill='#ffc0b0',width=1,tags='fx')
    elif style=='web':
        r=(8+6*k)*s
        for n in range(8):
            a=n*math.pi/4;c.create_line(px,py,px+math.cos(a)*r,py+math.sin(a)*r*.7,fill='#e8e8dc',width=1,tags='fx')
        for ring in (.45,.85):
            points=[v for n in range(9) for v in (px+math.cos(n*math.pi/4)*r*ring,py+math.sin(n*math.pi/4)*r*ring*.7)]
            c.create_line(*points,fill='#d8d8c8',width=1,tags='fx')
    elif style=='bite':
        r=11*s;gap=(1-min(1,k*2.2))*7*s;color='#f0e6d0' if hit else '#8f8a7c'
        c.create_arc(px-r,py-r-gap,px+r,py+r-gap,start=200,extent=140,style='arc',outline=color,width=max(1,2*s),tags='fx')
        c.create_arc(px-r,py-r+gap,px+r,py+r+gap,start=20,extent=140,style='arc',outline=color,width=max(1,2*s),tags='fx')
        for n in (-1,0,1):
            x=px+n*r*.45;c.create_line(x,py-gap-r*.55,x,py-gap-r*.25,fill=color,width=1,tags='fx')
            c.create_line(x,py+gap+r*.55,x,py+gap+r*.25,fill=color,width=1,tags='fx')
    elif style=='claw':
        grow=min(1,k*2.5);color='#ff8f79' if hit else '#a49a86'
        for n in (-1,0,1):
            x1,y1=px-9*s+n*5*s,py-10*s;x2,y2=px+7*s+n*5*s,py+9*s
            c.create_line(x1,y1,x1+(x2-x1)*grow,y1+(y2-y1)*grow,fill=color,width=max(1,2.2*s),capstyle='round',tags='fx')
    elif style=='smash':
        r=(6+26*k)*s;c.create_oval(px-r,py-r*.45,px+r,py+r*.45,outline='#d9cdb2',width=max(1,3*(1-k)+.5),tags='fx')
        for _ in range(4):
            a=rng.uniform(0,2*math.pi);points=[px,py];x,y=px,py
            for _ in range(3):
                x+=math.cos(a+rng.uniform(-.5,.5))*6*s;y+=math.sin(a+rng.uniform(-.5,.5))*3*s;points+=[x,y]
            c.create_line(*points,fill='#3a3426',width=max(1,1.6*s),tags='fx')
    else:  # punch
        r=(5+6*k)*s;points=[]
        for n in range(10):
            rr=r if n%2==0 else r*.45;a=n*math.pi/5
            points+=[px+math.cos(a)*rr,py+math.sin(a)*rr]
        c.create_polygon(*points,fill='#ffe3a0' if hit else '#a49a86',outline='',tags='fx')
