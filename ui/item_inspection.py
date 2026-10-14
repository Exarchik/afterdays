"""Compact, textured item card. All mutations use the game's normal actions."""
import tkinter as tk
from tkinter import ttk
import content
import sprites
import module_rules as mr
from game import items, catalog
from ui.window_skin import BG, GOLD, TEXT
from ui.widgets import Tooltip

GOOD, BAD, MUTED = '#91d9aa', '#ef9690', '#a5aa99'


def module_compatibility(item):
    from i18n import t as tr
    rules=mr.restrictions(item);target=rules.get('target',item.get('target'))
    if target=='weapon':
        categories=tuple(dict.fromkeys(rules.get('weapon_categories',mr.WEAPON_CATEGORIES)))
        value='Універсальний' if set(mr.WEAPON_CATEGORIES)<=set(categories) else ', '.join(tr('update033.category_'+c) for c in categories)
        return 'Сумісна зброя',value or 'Немає'
    return 'Сумісна броня',{'armor':'Броня','helmet':'Шоломи','protection':'Універсальний'}.get(target,str(target))


def summary_color(item,label,value):
    """Color effects by benefit; metadata such as price and weight stays neutral."""
    if item['kind'] in ('food','med','rad','repairkit'):
        from game.systems import consumables
        effects=consumables.definition(item)
        for key,(name,_,_) in consumables.FIELDS.items():
            if name==label and key not in ('value','weight'):
                amount=effects.get(key,0)
                return (GOOD if (amount<0 if key in ('damage_percent','ap_cost') else amount>0) else BAD) if amount else TEXT
    if label in ('Шкода пострілу','За повну шкалу ОД'):return GOOD
    if label=='Витрата ОД':return BAD
    if label in ('Захист','Дальність','Критичний шанс') or label in catalog.STAT_NAMES.values():
        try:amount=float(str(value).rstrip('%'))
        except ValueError:return TEXT
        lower=label==catalog.STAT_NAMES.get('weight_percent')
        return (GOOD if (amount<0 if lower else amount>0) else BAD) if amount else TEXT
    return TEXT


def owned(game,item):
    return any(i and i.get('id')==item.get('id') for i in [*game.bag,*game.equipped.values()])


def can_detach(game,item,module):
    return bool(not game.battle and owned(game,item) and not item.get('quest_id')
                and any(m.get('id')==module.get('id') for m in item.get('modules',[])))


def detach(game,item,module):
    if not can_detach(game,item,module):return False
    return game.uninstall(item['id'],module['id'])


def summary(game,item):
    """Rows are (label, display value, numeric comparison, lower-is-better)."""
    kind=item['kind'];rows=[]
    current=game.weapon if kind=='weapon' else game.equipped.get(kind)
    compare=current is not None and current['id']!=item.get('id')
    if 'durability' in item:rows.append(('Стан',mr.condition(item),None,False))
    if kind=='weapon':
        from damage_preview import estimate
        result=estimate(game,item);other=estimate(game,current) if compare else None
        s=mr.weapon_stats(game,item);base=mr.weapon_stats(game,current) if compare else {}
        diff=(result['minimum']-other['minimum'],result['maximum']-other['maximum']) if other else None
        rows.extend([
            ('Шкода пострілу',f"{result['minimum']}–{result['maximum']}",diff,False),
            ('За повну шкалу ОД',f"{result['total_minimum']}–{result['total_maximum']}",None,False),
            ('Витрата ОД',str(game.shot_ap(item)),game.shot_ap(item)-game.shot_ap(current) if compare else None,True),
            ('Дальність',str(s.get('range',0)),s.get('range',0)-base.get('range',0) if compare else None,False),
            ('Критичний шанс',f"{max(0,min(65,5+s.get('crit',0))+(15 if game.fire_mode(item)=='aimed' else 0)):g}%",None,False),
        ])
    elif kind in ('armor','helmet'):
        s=items.stats(item);base=items.stats(current) if compare else {}
        rows.append(('Захист',str(s.get('defense',0)),s.get('defense',0)-base.get('defense',0) if compare else None,False))
        for key in ('vitality','regen','evasion','capacity','defense_percent','reflect_percent'):
            if s.get(key):rows.append((catalog.STAT_NAMES.get(key,key),f"{s[key]:+g}"+('%' if key.endswith('_percent') or key=='evasion' else ''),None,False))
    elif kind=='module':
        label,value=module_compatibility(item)
        rows.insert(0,(label,value,None,False))
        for key,value in items.stats(item).items():
            if value:rows.append((catalog.STAT_NAMES.get(key,key),f'{value:+g}'+('%' if key in mr.PERCENT_STATS or key in ('accuracy','crit','evasion') else ''),None,False))
        rules=mr.restrictions(item)
        rows.append(('Рідкість спорядження','Від '+catalog.RARITIES[rules.get('min_equipment_rarity',0)][0].lower(),None,False))
    elif kind in ('food','med','rad','repairkit'):
        from game.systems import consumables
        d=consumables.definition(item)
        for key,(label,_,_) in consumables.FIELDS.items():
            if key not in ('value','weight','ap_cost') and d.get(key):rows.append((label,f'{d[key]:g}',None,False))
    if item.get('qty',1)>1:rows.append(('Кількість',str(item['qty']),None,False))
    weight=items.item_weight(item)
    rows.extend([('Вага',f'{weight:g} кг',weight-items.item_weight(current) if compare else None,True),
                 ('Вартість',f"{items.item_value(item):g} кр.",None,False)])
    return rows


class ItemCard(ttk.Frame):
    def __init__(self,win,app,item):
        super().__init__(win)
        self.win,self.app,self.item=win,app,item
        self.expanded=False;self.modules_open=False;self.targets=[];self.photo=None;self.job=None
        self.menu=None;self.tip_text='';self.parent_dialog=win.master
        self.pack(fill='both',expand=True)
        buttons=ttk.Frame(self);buttons.pack(side='bottom',pady=(8,0))
        self.equip_button=ttk.Button(buttons,text='Екіпірувати',command=self.equip)
        ttk.Button(buttons,text='Закрити',command=win.close_dialog).pack(side='right',padx=5)
        self.scroll=ttk.Scrollbar(self,orient='vertical');self.scroll.pack(side='right',fill='y')
        self.canvas=tk.Canvas(self,bg=BG,highlightthickness=0,yscrollcommand=self.scroll.set)
        self.canvas.pack(fill='both',expand=True);self.scroll.configure(command=self.canvas.yview)
        self.canvas.bind('<Configure>',self.schedule)
        self.canvas.bind('<MouseWheel>',self.wheel)
        self.canvas.bind('<Button-1>',self.click)
        self.canvas.bind('<Button-3>',self.context)
        self.canvas.bind('<Motion>',self.hover)
        self.tip=Tooltip(self.canvas,lambda:self.tip_text)
        self.canvas.unbind('<Enter>')
        self.bind('<Destroy>',self.destroyed)
        self.refresh()

    def destroyed(self,event):
        if event.widget is self and self.job:
            self.after_cancel(self.job);self.job=None

    def schedule(self,event=None):
        if not self.job:self.job=self.after_idle(self.draw)

    def refresh(self):
        from ui.item_actions import personal_actions
        # Failed capacity checks restore copied inventories; rebind to the live item.
        self.item=next((i for i in [*self.app.game.bag,*self.app.game.equipped.values()]
                        if i and i.get('id')==self.item.get('id')),self.item)
        self.equip_choices=[args[0] for code,args in personal_actions(self.app.game,self.item) if code=='equip']
        if self.equip_choices:self.equip_button.pack(side='left',padx=5)
        else:self.equip_button.pack_forget()
        self.schedule()

    def wheel(self,event):
        self.canvas.yview_scroll(-1 if event.delta>0 else 1,'units');return 'break'

    def text(self,x,y,text,size=11,color=TEXT,anchor='nw',width=0,bold=False):
        ident=self.canvas.create_text(x,y,text=text,fill=color,anchor=anchor,width=width,font=('Segoe UI',size,'bold' if bold else 'normal'))
        box=self.canvas.bbox(ident)
        return box[3] if box else y

    def draw(self):
        self.job=None;c=self.canvas;c.delete('all');self.targets=[]
        width=max(300,c.winfo_width());mods=self.item.get('modules',[])
        self.has_sidebar=bool(mods)
        main_right=width-(108 if self.has_sidebar else 16);left=16;main_width=main_right-left
        self.content_center=(left+main_right)/2
        self.text(self.content_center,10,self.item['name'],18,GOLD,'n',main_width,True)
        # Measure the title so long custom names never overlap the subtitle.
        title_end=c.bbox(c.find_all()[-1])[3]
        rarity=catalog.RARITIES[self.item.get('rarity',0)]
        subtitle=rarity[0]+(f" · Рівень {self.item.get('level',1)}" if self.item['kind'] in ('weapon','armor','helmet','module') else '')
        self.text(self.content_center,title_end+5,subtitle,10,rarity[1],'n',main_width)
        art_y=title_end+32
        image=sprites.photo(c,sprites.item_key(self.item),192)
        if image:
            from PIL import Image,ImageTk
            art=ImageTk.getimage(image);bbox=art.getbbox()
            if bbox:art=art.crop(bbox)
            scale=min((main_width-32)/art.width,142/art.height)
            art=art.resize((max(1,round(art.width*scale)),max(1,round(art.height*scale))),Image.Resampling.LANCZOS)
            self.photo=ImageTk.PhotoImage(art,master=c)
            c.create_image(self.content_center,art_y+71,image=self.photo)
        else:
            from visuals import icon
            icon(c,self.item,self.content_center-64,art_y+7,128,badge=False)
        y=art_y+156;self.rows=summary(self.app.game,self.item)
        vx=left+main_width*.65;dx=main_right-1
        for label,value,diff,lower in self.rows:
            if label=='Стан':
                self.text(left,y,label)
                x=left+main_width*.46;end=main_right-54
                c.create_rectangle(x,y+4,end,y+16,fill='#252b20',outline='#78653e')
                c.create_rectangle(x+1,y+5,x+1+max(0,end-x-2)*value/100,y+15,fill='#899349' if value>25 else '#b67552',outline='')
                self.text(main_right,y,f'{value:g}%',anchor='ne');y+=31
                c.create_line(left,y-5,main_right,y-5,fill='#796039');continue
            color=summary_color(self.item,label,value)
            end_label=self.text(left,y,label,color=color,width=main_width*.56)
            value_width=main_right-vx if label in ('Сумісна зброя','Сумісна броня') else max(50,main_width*.26)
            end_value=self.text(vx,y,str(value),color=color,width=value_width)
            if diff and (not isinstance(diff,tuple) or any(diff)):
                if isinstance(diff,tuple):
                    label_diff=f'{diff[0]:+g} / {diff[1]:+g}'
                    good=all(n>=0 for n in diff);bad=all(n<=0 for n in diff)
                    color=GOOD if good else BAD if bad else GOLD
                else:label_diff=f'{diff:+g}';color=GOOD if (diff<0 if lower else diff>0) else BAD
                self.text(dx,y+1,label_diff,9,color,'ne')
            y=max(end_label,end_value)+8
        if self.item['kind']=='weapon':
            y=self.text(left,y+2,'Шкода розрахована для останньої цілі пострілу.\nЗелені / червоні значення — різниця з екіпованим предметом.',9,MUTED,width=main_width)+10
        if self.has_sidebar:
            x=width-90;sy=50;size=64
            self.text(x,sy,'Модулі',11,GOLD,bold=True)
            self.text(x,sy+23,f"{len(mods)} із {max(len(mods),self.item.get('slots',0))}",10,MUTED)
            sy+=49
            for n in range(max(len(mods),self.item.get('slots',0))):
                mod=mods[n] if n<len(mods) else None
                color=catalog.RARITIES[mod.get('rarity',0)][1] if mod else '#78653e'
                c.create_rectangle(x,sy,x+size,sy+size,fill='#161d18',outline=color,width=2)
                if mod:
                    from visuals import icon
                    icon(c,mod,x+4,sy+4,size-8,badge=False)
                    self.targets.append((x,sy,x+size,sy+size,'module',mod))
                else:self.text(x+size/2,sy+size/2,'+',22,MUTED,'center')
                sy+=size+12
            self.text(x,sy,'ПКМ — дії',9,MUTED,width=82)
            sidebar_end=sy+30
        else:sidebar_end=0
        if 'slots' in self.item:
            label=f"{'▾' if self.modules_open else '▸'} Модулі · {len(mods)} із {self.item['slots']}"
            y=self.accordion(left,y+10,main_right,label,'modules')
            if self.modules_open:
                for mod in mods:
                    y=self.text(left+12,y,mod['name'],10,catalog.RARITIES[mod.get('rarity',0)][1],width=main_width-15)+4
                    bonuses=' · '.join(f'{catalog.STAT_NAMES.get(k,k)} {v:+g}' for k,v in items.stats(mod).items() if v)
                    y=self.text(left+12,y,bonuses,9,TEXT,width=main_width-15)+10
                if not mods:y=self.text(left+12,y,'Немає встановлених модулів',10,MUTED,width=main_width-15)+8
        y=self.accordion(left,y+6,main_right,('▾' if self.expanded else '▸')+' Детальні характеристики','details')
        if self.expanded:
            from ui.refinement import description
            detail=description(self.app.game,self.item)
            y=self.detail_table(left+8,y,main_right-4,detail)+12
        self.content_height=max(y+16,sidebar_end)
        c.configure(scrollregion=(0,0,width,max(c.winfo_height(),self.content_height)))

    def detail_table(self,left,y,right,detail):
        """Render the existing tab-separated comparison as independent columns."""
        from i18n import t as tr
        width=right-left
        edges=(left,left+width*.52,left+width*.78,right)
        for line in detail.splitlines():
            if not line.strip():y+=8;continue
            cells=line.split('\t',2)
            if len(cells)==1:
                y=self.text(left,y,line.replace('[+]','').replace('[-]',''),10,TEXT,width=width)+8
                continue
            header=line==tr('refinement_ui.0005')
            if header:y+=4
            bottom=y
            for n,value in enumerate(cells):
                color=GOLD if header else GOOD if '[+]' in value else BAD if '[-]' in value else TEXT
                value=value.replace('[+]','').replace('[-]','').strip()
                # Every cell wraps within its own column; tallest cell sets row height.
                bottom=max(bottom,self.text(edges[n]+4,y,value,10,color,
                                           width=max(20,edges[n+1]-edges[n]-12),bold=header))
            self.canvas.create_line(left,bottom+5,right,bottom+5,
                                    fill='#796039' if header else '#344139')
            y=bottom+12
        return y

    def accordion(self,x,y,right,label,action):
        self.text(x,y,label,11,GOLD)
        self.targets.append((x,y,right,y+25,action,None));return y+31

    def hit(self,event):
        x,y=self.canvas.canvasx(event.x),self.canvas.canvasy(event.y)
        return next(((action,item) for a,b,c,d,action,item in self.targets if a<=x<=c and b<=y<=d),None)

    def hover(self,event):
        hit=self.hit(event);self.canvas.configure(cursor='hand2' if hit else '')
        text=(hit[1]['name']+'\nПКМ — дії з модулем') if hit and hit[0]=='module' else ''
        if text!=self.tip_text:
            self.tip_text=text;self.tip.hide()
            if text:
                self.tip.show()
                self.tip.win.geometry(f'+{event.x_root+14}+{event.y_root+14}')

    def click(self,event):
        self.tip.hide()
        hit=self.hit(event)
        if not hit:return
        action,mod=hit
        if action=='module':
            from ui.inspection import inspect_item
            inspect_item(self.app,mod)
        elif action=='details':self.expanded=not self.expanded;self.draw()
        elif action=='modules':self.modules_open=not self.modules_open;self.draw()

    def context(self,event):
        self.tip.hide()
        hit=self.hit(event)
        if not hit or hit[0]!='module':return
        mod=hit[1]
        if self.menu:self.menu.destroy()
        self.menu=tk.Menu(self.canvas,tearoff=False,bg='#252b21',fg=TEXT,activebackground='#51452c')
        from ui.inspection import inspect_item
        self.menu.add_command(label='Характеристики',command=lambda:inspect_item(self.app,mod))
        self.menu.add_command(label='Вийняти в інвентар',state='normal' if can_detach(self.app.game,self.item,mod) else 'disabled',command=lambda:self.remove(mod))
        try:self.menu.tk_popup(event.x_root,event.y_root)
        finally:
            self.menu.grab_release()
            if self.win.winfo_exists():self.win.grab_set()
        return 'break'

    def run(self,fn):
        self.app.act(fn)
        # Refresh an underlying workshop/shop after its inspected item changes.
        def refresh_children(widget):
            for child in widget.winfo_children():
                if isinstance(child,tk.Toplevel):continue
                if hasattr(child,'refresh') and hasattr(child,'app'):child.refresh()
                else:refresh_children(child)
        if self.parent_dialog is not self.app.root and self.parent_dialog.winfo_exists():refresh_children(self.parent_dialog)
        self.refresh()

    def remove(self,mod):self.run(lambda:detach(self.app.game,self.item,mod))

    def equip(self):
        from ui.item_actions import personal_actions
        choices=[args[0] for code,args in personal_actions(self.app.game,self.item) if code=='equip']
        if choices:
            slot=self.app.game.active if self.app.game.active in choices else choices[0]
            self.run(lambda:self.app.game.equip(self.item['id'],slot))
