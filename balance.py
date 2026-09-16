"""Shared combat and progression balance; no runtime UI dependencies."""
import content
import math
WEAPON_ATTACK = content.WEAPON_ATTACK
MONSTER_STATS = content.MONSTER_STATS
TRAVELER_WEIGHTS=[30,40,22,7,1]
def attack_for(name,level):return WEAPON_ATTACK[name]+2*(level-1)
def set_monster(enemy):
 content.identify_monster(enemy)
 data=content.MONSTER_DATA[enemy['type_id']]
 attack,defense=data['attack'],data['defense']
 bonus=2*(enemy.get('level',1)-1)+{'normal':0,'rare':2,'mythic':4}[enemy.get('grade','normal')]
 enemy.update(attack=attack+bonus,defense=defense+bonus,armor=defense+bonus)
def multiplier(attack,defense):
 delta=max(0,attack)-max(0,defense)
 return 1+.05*delta if delta>=0 else 1/(1-.05*delta)
def damage(raw,attack,defense):return max(1,math.floor(max(0,raw)*multiplier(attack,defense)+.5))
def level_cost(level):return 120*level+24*level*max(0,level-4)
def xp_threshold(level):
 n=max(0,level-1)
 return 60*n*(n+1)+(24*(n*(n+1)*(2*n+1)//6-30-4*(n*(n+1)//2-10)) if n>4 else 0)
def migrate_xp(xp):
 level=1
 while 60*level*(level+1)<=xp:level+=1
 old=60*(level-1)*level
 return xp_threshold(level)+(xp-old)*level_cost(level)//(120*level)
