"""Weapon categories, atomic firing modes and condition-dependent attacks."""
import math
import content,hexgrid,balance
import progression as p
from i18n import t as tr


def category(item):
    return content.EQUIPMENT.get(item.get('type_id'),{}).get('category','pistol') if item else 'pistol'

def modes(item):
    kind=category(item)
    return ('single','burst') if kind=='automatic' else ('aimed',) if kind=='sniper' else ('single',)

def shot_cost(item):
    allowed=modes(item);mode=item.get('fire_mode',allowed[0])
    if mode not in allowed:mode=allowed[0]
    return item.get('ap',2)+int(mode in ('aimed','burst'))

def misfire_chance(item):
    condition=p.mr.condition(item)
    return 0 if condition>=75 else .02 if condition>=50 else .05

def behind(source,target,pos):
    """A narrow axial-space cone extending at most three hexes beyond the target."""
    def point(a):return (a[0]+a[1]*.5,a[1]*math.sqrt(3)/2)
    a,b,c=map(point,(source,target,pos));dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
    if not length:return False
    vx,vy=c[0]-b[0],c[1]-b[1]
    return 0<(vx*dx+vy*dy)/length<=3.1 and abs(vx*dy-vy*dx)/length<=1.1

def projectile_components(weapon,level,enemy,variation,critical,pellet=None,multiplier=1):
    """Pure damage formula shared by combat and weapon previews."""
    from adventure import damage_type,RESISTANCES
    stats=p.stats(weapon)
    components=p.mr.shot_components(weapon,level,variation,damage_type(weapon))
    dealt={}
    for element,raw in components.items():
        base=balance.damage(raw*(1.6 if critical else 1),stats.get('attack',0),enemy.get('defense',enemy.get('armor',0)))
        resist=enemy.get('resists',RESISTANCES.get(enemy.get('kind'),{})).get(element,0)
        amount=max(1,round(base*(1-resist/100))) if raw else 0
        if amount:amount=max(1,round(amount*multiplier))
        if pellet is not None:amount=amount//6+int(pellet<amount%6)
        dealt[element]=amount
    return dealt


class Combat:
    def fire_modes(self,weapon=None):
        """Return modes available for the selected weapon category."""
        return modes(weapon or self.weapon)

    def fire_mode(self,weapon=None):
        """Resolve the stored mode, repairing obsolete modes without mutating an item."""
        weapon=weapon or self.weapon;allowed=modes(weapon)
        value=weapon.get('fire_mode') if weapon else None
        return value if value in allowed else allowed[0]

    def cycle_fire_mode(self):
        """Switch between single and burst without spending AP."""
        if not self.battle or not self.weapon or len(self.fire_modes())<2:return False
        self.weapon['fire_mode']='burst' if self.fire_mode()=='single' else 'single';return True

    def shot_ap(self,weapon=None):
        """Calculate AP including automatic burst or aimed-shot surcharge."""
        weapon=weapon or self.weapon
        return shot_cost(weapon) if weapon else 0

    def shot_info(self,enemy):
        """Keep range/line-of-sight rules and apply mode accuracy in percentage points."""
        valid,reason,chance=super().shot_info(enemy)
        if valid:
            mode=self.fire_mode()
            if mode=='burst':chance-=15
            elif mode=='aimed':chance+=-30 if hexgrid.distance(self.battle['pos'],enemy['pos'])<4 else 10
            chance=max(1,min(98,chance))
        return valid,reason,chance

    def _projectile_damage(self,enemy,weapon,mode,pellet=None):
        """Resolve one bullet or one sixth of a shotgun shell after defense/resistance."""
        from adventure import damage_type,RESISTANCES,DAMAGE_TYPES
        stats=p.stats(weapon);critical=self.rng.randrange(100)<(min(65,5+stats.get('crit',0))+(15 if mode=='aimed' else 0))
        dealt=projectile_components(weapon,self.level,enemy,self.rng.randint(-2,2),critical,pellet,getattr(self,'outgoing_damage_multiplier',1))
        amount=sum(dealt.values());enemy['hp']-=amount;enemy['awake']=True
        self.emit((tr('adventure.0217') if critical else '')+f'−{amount}',pos=enemy['pos'],color='#ffbf82' if critical else '#ff9d84')
        self.log(f'{enemy["name"]}: −{amount} HP ('+', '.join(f'{DAMAGE_TYPES[k][0]}: {v}' for k,v in dealt.items())+').')
        if enemy['hp']<=0:self._finish_enemy(enemy,weapon)

    def shoot(self,enemy_id):
        """Spend AP/ammunition once, animate every projectile and finish all hits before victory."""
        from adventure import damage_type,DAMAGE_TYPES
        b=self.battle;w=self.weapon
        if not b or not w:return False
        target=next((e for e in b['enemies'] if e['id']==enemy_id),None)
        if not target:return False
        valid,why,chance=self.shot_info(target);mode=self.fire_mode();bullets=5 if mode=='burst' else 1
        ammo=w.get('ammo_type','pistol');reason=None
        if p.mr.condition(w)<=0:reason=tr('adventure.0213')
        elif self.count('ammo',ammo)<bullets:reason=tr('update033.ammo_need',qty=bullets)
        elif b['ap']<self.shot_ap():reason=tr('adventure.0215')
        elif not valid:reason=why
        if reason:self.log(reason);self.emit(reason,color='#ffcb79');return False
        from damage_preview import remember_target
        remember_target(self,target)
        b['ap']-=self.shot_ap();saved=p.mr.chance(p.stats(w).get('ammo_save_percent',0))
        for _ in range(bullets):
            if saved and self.rng.random()*100<saved:self.emit(tr('modules.ammo_saved'),color='#9cdcd8')
            else:self.consume('ammo',1,ammo)
        shell=category(w)=='shotgun';count=6 if shell else bullets
        targets=[e for e in b['enemies'] if e is not target and behind(b['pos'],target['pos'],e['pos']) and hexgrid.visible(tuple(b['pos']),tuple(e['pos']),b['walls'])]
        targets.sort(key=lambda e:hexgrid.distance(target['pos'],e['pos']))
        misfire=self.rng.random()<misfire_chance(w) if misfire_chance(w) else False
        stray=None
        if misfire:
            self.emit(tr('update033.jam'),color='#ffc46e')
            pool=[e for e in b['enemies'] if e is not target and hexgrid.distance(b['pos'],e['pos'])<=p.stats(w)['range'] and hexgrid.visible(tuple(b['pos']),tuple(e['pos']),b['walls'])]
            if pool and self.rng.random()<.25:stray=self.rng.choice(pool)
        for n in range(count):
            hit=None
            if misfire:
                if stray in b['enemies'] and self.rng.randrange(100)<chance:hit=stray
            elif target in b['enemies'] and self.rng.randrange(100)<chance:hit=target
            elif shell:
                for enemy in targets:
                    if enemy in b['enemies'] and self.rng.randrange(100)<max(1,chance-15):hit=enemy;break
            pos=(hit or target)['pos']
            self.emit(kind='attack',pos=pos,source=b['pos'],color=DAMAGE_TYPES[damage_type(w)][1])
            self._events[-1].update(fire_mode='pellet' if shell else mode,projectile=n)
            if hit:self._projectile_damage(hit,w,mode,n if shell else None)
            else:self.emit(tr('adventure.0218'),pos=pos,color='#d7d4c0')
        target['awake']=True
        self.wear(w,.6*bullets*(2 if mode=='aimed' else 1))
        if not b['enemies']:self.victory()
        return True
