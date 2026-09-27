"""Field-terminal player header. Rendering has no effect on game rules or saves."""
import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
import progression as p
import sprites
from i18n import t as tr
from interface032 import Tooltip
from visuals import TEXT,GOLD,MUTED,icon

BG='#17221d'
LINE='#52604b'
GREEN='#58b879'

def snapshot(g):
    """Read the current game into display values, including level-relative XP."""
    start=p.xp_for_level(g.level);goal=p.xp_for_level(g.level+1)
    w=g.weapon;ammo=w.get('ammo_type','pistol') if w else None
    return dict(level=g.level,hp=g.hp,max_hp=g.max_hp,xp=g.xp-start,xp_goal=goal-start,
                defense=g.defense,weight=g.weight,capacity=g.capacity,money=g.money,turn=g.turn,
                weapon=w,ammo=p.AMMO[ammo][0] if ammo else '',rounds=g.count('ammo',ammo) if ammo else 0,
                cost=g.shot_ap(w) if w else 0,mode=g.fire_mode(),modes=g.fire_modes(),
                other=g.equipped.get('weapon2' if g.active=='weapon1' else 'weapon1'),
                ap=g.battle['ap'] if g.battle else None,
                max_ap=max(g.battle.get('max_ap',g.max_ap),g.battle['ap']) if g.battle else g.max_ap,
                coward=g.coward_turns,rad=g.rad_turns)

def sections(width):
    """Allocate proportional header columns at both minimum and wide window sizes."""
    ratios=(.12,.23,.28,.14,.12,.11);edges=[0]
    for ratio in ratios:edges.append(edges[-1]+width*ratio)
    return list(zip(edges,edges[1:]))

class StatusBar(tk.Canvas):
    def __init__(self,parent,app):
        """Create one canvas with bounded sprite caching and contextual hover targets."""
        super().__init__(parent,height=108,bg=BG,highlightthickness=1,highlightbackground=LINE)
        self.app=app;self.game=None;self.regions=[];self.hover=None;self.tip_text='';self.signature=None
        self.tip=Tooltip(self,lambda:self.tip_text)
        self.unbind('<Enter>')
        self.bind('<Configure>',lambda e:self.paint())
        self.bind('<Motion>',self.motion);self.bind('<Leave>',self.leave)
        self.bind('<Button-1>',self.click);self.bind('<Button-3>',self.context)
        self.fonts={}

    def text(self,x,y,value,size=10,color=TEXT,width=None,anchor='w',bold=False):
        """Draw a single fitted text line; full names remain available in tooltips."""
        key=(size,bold)
        if key not in self.fonts:self.fonts[key]=tkfont.Font(self,family='Segoe UI',size=size,weight='bold' if bold else 'normal')
        font=self.fonts[key];value=str(value)
        if width is not None:
            original=value
            while value and font.measure(value)>max(1,width):value=value[:-1]
            if value!=original:
                while value and font.measure(value+'…')>max(1,width):value=value[:-1]
                value+='…'
        self.create_text(x,y,text=value,font=font,fill=color,anchor=anchor)

    def glyph(self,kind,x,y,color=GOLD):
        """Draw small readable vector symbols without platform-dependent emoji fonts."""
        if kind=='shield':
            self.create_polygon(x,y-9,x+8,y-6,x+7,y+3,x,y+9,x-7,y+3,x-8,y-6,fill='',outline=color,width=2)
        elif kind=='pack':
            self.create_line(x-4,y-7,x-4,y-11,x+4,y-11,x+4,y-7,fill=color,width=2)
            self.create_rectangle(x-8,y-7,x+8,y+9,outline=color,width=2)
            self.create_rectangle(x-5,y+1,x+5,y+6,outline=color)
        elif kind=='coins':
            for offset in (5,0,-5):self.create_oval(x-8,y+offset-3,x+8,y+offset+3,outline=color,width=2)
        elif kind=='clock':
            self.create_oval(x-8,y-8,x+8,y+8,outline=color,width=2)
            self.create_line(x,y-5,x,y,x+4,y,fill=color,width=2)

    def region(self,box,tip,action=None):
        """Register a visible hover area and its optional click action."""
        self.regions.append((box,tip,action))

    def refresh(self,g):
        """Update immediately on game refresh, while skipping unchanged header redraws."""
        self.game=g
        signature=repr(snapshot(g))
        if signature!=self.signature:self.signature=signature;self.paint()

    def paint(self):
        """Render the six terminal blocks using current data and available width."""
        if self.game is None:return
        g=self.game;d=snapshot(g);self.tip.hide();self.hover=None;self.regions=[];self.delete('all')
        width=max(1,self.winfo_width()-2);cols=sections(width);compact=width<1350
        for a,b in cols[:-1]:self.create_line(b,12,b,96,fill=LINE)
        a,b=cols[0];size=48 if compact else 64
        # Use the existing survivor artwork; no new image dependency at runtime.
        sprites.draw(self,'npc:traveler',a+7,20,size)
        self.text(b-25,36,d['level'],22,GOLD,anchor='center',bold=True)
        self.text(b-25,65,tr('terminal.level'),8,GOLD,anchor='center')
        self.region((a,0,b,108),tr('terminal.player'),lambda:self.app.tabs.select(self.app.player_tab))
        a,b=cols[1];x=a+14;right=b-14;barw=right-x
        for label,amount,total,y,color in [(tr('terminal.hp'),d['hp'],d['max_hp'],19,'#d9655b' if d['hp']<=d['max_hp']*.25 else GREEN),(tr('terminal.xp'),d['xp'],d['xp_goal'],65,'#c9ae41')]:
            self.text(x,y,label,8,MUTED,width=barw*.43);self.text(right,y,f'{amount:g} / {total:g}',10,TEXT,width=barw*.55,anchor='e',bold=True)
            self.create_rectangle(x,y+12,right,y+20,fill='#29382d',outline='')
            ratio=min(1,max(0,amount/max(1,total)))
            if ratio:self.create_rectangle(x,y+12,x+barw*ratio,y+20,fill=color,outline='')
        self.region((a,0,b,108),tr('terminal.progress',level=g.level,left=max(0,d['xp_goal']-d['xp'])))
        a,b=cols[2];art=48 if compact else 64;left=a+art+14;right=b-10
        if d['weapon']:icon(self,d['weapon'],a+6,17,art)
        name=d['weapon']['name'] if d['weapon'] else tr('update030.no_weapon')
        self.text(left,17,name,10,GOLD,width=right-left,bold=True)
        self.text(left,38,f"{d['ammo']} · {d['rounds']}" if d['weapon'] else '—',9,MUTED,width=right-left-34)
        swapcolor=GOLD if d['other'] else LINE
        self.text(right-9,39,'⇄',20,swapcolor,anchor='center')
        self.region((right-28,27,right+3,53),tr('terminal.swap') if d['other'] else tr('terminal.no_second'),lambda:self.app.act(self.app.game.switch) if self.app.game.equipped.get('weapon2' if self.app.game.active=='weapon1' else 'weapon1') else None)
        mode=tr('update033.mode_'+d['mode'])
        self.text(left,59,tr('terminal.shot',cost=d['cost'])+' · '+mode,9,TEXT,width=right-left)
        self.region((left,49,right,70),tr('terminal.mode'),(lambda:self.app.act(self.app.game.cycle_fire_mode)) if g.battle and len(d['modes'])>1 else None)
        if d['ap'] is not None:
            self.text(left,84,f"{d['ap']}/{d['max_ap']}",9,GOLD)
            n=d['max_ap'];step=min(13,max(2,(right-left-45)/max(1,n)))
            for i in range(n):
                x=left+43+i*step
                self.create_rectangle(x,79,x+max(1,step-3),89,fill=GREEN if i<d['ap'] else '#59615e',outline='')
        else:self.text(left,83,tr('terminal.condition',value=round(d['weapon'].get('durability',100))) if d['weapon'] else '',8,MUTED,width=right-left)
        self.region((a,0,b,108),name+'\n'+tr('terminal.weapon_tip'))
        a,b=cols[3];x=a+12
        self.text(x,18,tr('terminal.defense'),8,MUTED);self.glyph('shield',x+8,39);self.text(x+25,39,d['defense'],17,GOLD,bold=True)
        self.text(x,63,tr('terminal.weight'),8,MUTED)
        self.glyph('pack',x+8,85);self.text(x+25,85,f"{d['weight']:.1f}/{d['capacity']:g}",11,'#e17766' if d['weight']>d['capacity'] else GOLD if d['weight']>=d['capacity']*.85 else TEXT,width=b-x-33,bold=True)
        self.region((a,0,b,108),tr('terminal.weight_tip'))
        a,b=cols[4];x=a+12
        self.text(x,18,tr('terminal.money'),8,MUTED);self.glyph('coins',x+8,43);self.text(x+25,43,f"{d['money']:,}".replace(',',' '),17,GOLD,width=b-x-33,bold=True)
        self.glyph('clock',x+8,81);self.text(x+25,81,str(d['turn']),10,TEXT,width=b-x-33)
        self.region((a,0,b,108),tr('terminal.money_tip',money=d['money'],turn=d['turn']))
        a,b=cols[5];x=a+10;self.text(x,18,tr('terminal.effects'),8,GOLD)
        effects=[]
        if d['rad']:effects.append((tr('terminal.rad',turns=d['rad']),GREEN))
        if d['coward']:effects.append((tr('terminal.coward',turns=d['coward']),'#e17766'))
        for n,(label,color) in enumerate(effects):self.text(x,44+n*27,label,9,color,width=b-x-7)
        if not effects:self.text(x,56,'—',18,MUTED)
        self.region((a,0,b,108),'\n'.join(([tr('terminal.rad_tip',turns=d['rad'])] if d['rad'] else [])+([tr('terminal.coward_tip',turns=d['coward'])] if d['coward'] else [])) or tr('terminal.no_effects'))

    def target(self,event):
        """Find the first matching hit area, giving small controls priority."""
        return next((n for n,(box,tip,action) in enumerate(self.regions) if box[0]<=event.x<=box[2] and box[1]<=event.y<=box[3]),None)

    def motion(self,event):
        """Update hover help only when the cursor enters a different control."""
        target=self.target(event)
        if target==self.hover:return
        self.hover=target;self.tip.hide()
        if target is not None:
            box,self.tip_text,action=self.regions[target];self.config(cursor='hand2' if action else '')
            self.tip.show()
        else:self.config(cursor='')

    def leave(self,event=None):
        """Clear hover state and close transient help when leaving the header."""
        self.hover=None;self.tip.hide();self.config(cursor='')

    def click(self,event):
        """Dispatch only explicit portrait, swap and fire-mode controls."""
        target=self.target(event)
        if target is not None:
            action=self.regions[target][2]
            if action:self.tip.hide();action()

    def context(self,event):
        """Open the existing item context menu on the weapon block."""
        a,b=sections(max(1,self.winfo_width()-2))[2]
        if a<=event.x<=b and self.app.game.weapon:
            from item_actions import show
            self.tip.hide();show(self.app,self.app.game.weapon,event,self)

def system_menu(parent,app):
    """Keep all former title-bar commands in a single accessible dropdown."""
    button=ttk.Menubutton(parent,text=tr('terminal.menu'));menu=tk.Menu(button,tearoff=False,bg=BG,fg=TEXT,activebackground='#344238',activeforeground=GOLD)
    for label,command in [(tr('afterdays.0136'),app.save),(tr('afterdays.0135'),app.load),(tr('afterdays.0134'),app.new),('?',app.help),(tr('afterdays.0133'),lambda:sprites.gallery(app))]:menu.add_command(label=label,command=command)
    button.configure(menu=menu);button.menu=menu;button.pack(side='right',padx=3)
    return button
