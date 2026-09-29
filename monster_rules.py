"""Species progression shared by wilderness, dungeons and quest encounters."""
import copy,uuid
import content,balance
from i18n import t as tr


def base_level(kind):return content.MONSTER_DATA[content.monster_id(kind)]['base_level']
def eligible(zone,weak=True):
    return [i for i in range(len(content.MONSTER_IDS)) if base_level(i)<=zone+(1 if weak else 0)]

def choose(rng,zone):
    pool=eligible(zone)
    return rng.choices(pool,[spawn_weight(k,zone) for k in pool])[0]

def spawn_weight(kind,zone):
    base=base_level(kind)
    return (0.3 if base>zone else 1.0)/(1+abs(zone-base))**2

def make(rng,kind,zone,pos,grade=None,weak=None,boost=1):
    ident=content.monster_id(kind);d=content.MONSTER_DATA[ident];base=d['base_level']
    weak=base>zone if weak is None else weak
    grade=grade or rng.choices(['normal','rare','mythic'],[91,8,1])[0]
    e=dict(id=uuid.uuid4().hex,kind=d['legacy_index'],type_id=ident,name=content.name(ident),pos=list(pos),
           **definition_values(d,grade,weak,boost))
    e['name']=(tr('monster.grade.'+grade) if grade!='normal' else '')+content.name(ident)+(tr('exp.weak') if weak else '')
    return e

def definition_values(d,grade='normal',weak=False,boost=1):
    """Species scaling independent of catalog identity, shared with editor previews."""
    base=d['base_level'];level=max(1,base-1 if weak else base)
    hp=round(d['hp']*(1+.24*(level-1))*{'normal':1,'rare':1.5,'mythic':2.5}[grade]*boost*(.8 if weak else 1))
    e=dict(hp=max(1,hp),max_hp=max(1,hp),damage=max(1,round((d['damage']+3*(level-1))*{'normal':1,'rare':1.3,'mythic':1.8}[grade]*boost*(.8 if weak else 1))),
           range=d['range'],speed=d['speed'],color=d['color'],level=level,grade=grade,weak=bool(weak),base_level=base,
           resists=copy.deepcopy(d['resists']),armor=d['armor'])
    bonus=2*(level-1)+{'normal':0,'rare':2,'mythic':4}[grade]
    e.update(attack=d['attack']+bonus,defense=d['defense']+bonus,armor=d['defense']+bonus)
    if weak:e['attack']=max(1,e['attack']-2);e['defense']=max(0,e['defense']-2);e['armor']=e['defense']
    return e
