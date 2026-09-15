"""Shared combat and progression balance; no runtime UI dependencies."""
import math
WEAPON_ATTACK={'Пістолет «Попіл»':10,'Револьвер «Ворон»':12,'ПП «Шершень»':8,'Дробовик «Грім»':6,
 'Гвинтівка «Сторож»':13,'Автомат «Іржа»':10,'Арбалет «Тиша»':11,'Карабін «Пілігрим»':12,
 'Іонний пістолет «Іскра»':13,'Лазер «Промінь»':14,'Снайперська «Горизонт»':16,
 'Кулемет «Молот»':9,'Плазмомет «Сонце»':12,'Гаус-карабін «Імпульс»':18}
MONSTER_STATS=[(6,2),(9,5),(11,3),(12,4),(8,15),(13,8),(14,6),(15,12),(10,10),(12,16),(17,5),(13,9)]
TRAVELER_WEIGHTS=[30,40,22,7,1]
def attack_for(name,level):return WEAPON_ATTACK[name]+2*(level-1)
def set_monster(enemy):
 attack,defense=MONSTER_STATS[enemy['kind']]
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
