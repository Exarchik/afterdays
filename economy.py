from i18n import t as tr
"""v0.9 monster-dependent loot, trophy trade and fixed quest contracts."""
import copy,json,math
import content
from pathlib import Path
import afterdays as r
import progression as p
import adventure as a
if len(r.MERCHANTS)==4:r.MERCHANTS.append(tr('economy.0001'))
p.STACK_KINDS.add('trophy')
HUNTER_CITIES=(0,3,5,9)
BODY_NAMES=[content.t(k+'.trophy') for k in content.MONSTER_IDS]
BASE_REWARDS={'scout':45,'hunt':70,'retrieve':85,'purge':110,'supplies':40,'trophies':60}
WEIGHTS=[55,27,12,5,1]
def trophy(kind,qty=1):
 kind=content.MONSTER_DATA[content.monster_id(kind)]['legacy_index']
 return dict(id=r.uid(),type_id='trophy_'+content.monster_id(kind),monster_type_id=content.monster_id(kind),kind='trophy',name=BODY_NAMES[kind],monster_kind=kind,rarity=0,level=1,qty=qty,weight=.08,value=content.MONSTER_DATA[content.monster_id(kind)].get('trophy_value',2*(4+kind)))
def loot_rules(kills):
 normal=sum(e.get('grade','normal')=='normal' for e in kills);rare=sum(e.get('grade')=='rare' for e in kills);mythic=sum(e.get('grade')=='mythic' for e in kills)
 return min(1,.10+.05*normal+.10*rare+.25*mythic)*.25,2+rare+2*mythic,4 if mythic else 3 if rare else 1
class Game(a.Game):
 def __init__(self,seed=None):
  """Ініціалізує об’єкт, його початковий стан і потрібні залежності."""
  super().__init__(seed);self.add_hunters()
 def add_hunters(self):
  """Додає мисливців до наборів торговців поселень."""
  for n in HUNTER_CITIES:
   if 4 not in self.city_merchants[n]:self.city_merchants[n].append(4)
 def available_merchant(self,m):
  """Перевіряє доступність вказаного торговця у поточній локації."""
  roaming=self.traveler and self.traveler.get('hunter') and self.traveler['pos']==[self.x,self.y]
  if m==4:return not self.battle and (bool(roaming) or self.city in HUNTER_CITIES)
  if m==3 and roaming:return False
  return super().available_merchant(m)
 # Повертає назву торговця для інтерфейсу.
 def merchant_title(self,m):return tr('economy.0002') if m==4 else super().merchant_title(m)
 def stock(self,m):
  """Повертає або оновлює асортимент торговця."""
  if m==4:return []
  return super().stock(m)
 def spawn_traveler(self):
  """Обирає й створює випадкового мандрівника поблизу гравця."""
  if self.rng.random()<.30:
   self.traveler=dict(hunter=True,pos=[self.x,self.y],items=[]);self.last_traveler_turn=self.turn;self.log(tr('economy.0003'))
  else:super().spawn_traveler()
 def buys_kind(self,item,m):
  """Перевіряє, чи приймає торговець цей предмет."""
  if m==4:return item['kind']=='trophy'
  if item['kind']=='trophy':return m in (1,2,3)
  return super().buys_kind(item,m)
 def price(self,item,m,buying=True):
  """Обчислює ціну купівлі або продажу предмета."""
  if item['kind']=='trophy' and not buying:return item['value']*(2 if m==4 else 1)
  return super().price(item,m,buying)
 # Рахує доступні трофеї вказаного виду монстра.
 def trophy_count(self,kind):return sum(i.get('qty',1) for i in self.bag if i['kind']=='trophy' and content.monster_id(i.get('monster_type_id',i['monster_kind']))==content.monster_id(kind))
 def consume_trophies(self,kind,qty):
  """Вилучає потрібну кількість трофеїв із сумки."""
  for item in list(self.bag):
   if item['kind']=='trophy' and content.monster_id(item.get('monster_type_id',item['monster_kind']))==content.monster_id(kind):
    take=min(qty,item['qty']);p.extract(self.bag,item,take);qty-=take
    if not qty:break
 def reward_item(self,cap=4,minimum=0,level=None):
  """Генерує спорядження для нагороди з обмеженнями рівня й рідкості."""
  tier=self.rng.choices(list(range(minimum,cap+1)),WEIGHTS[minimum:cap+1])[0]
  level=self.rng.randint(max(1,self.level-2),self.level) if level is None else max(1,int(level))
  category=self.rng.choice(['weapon','armor','helmet','module'])
  if category=='module':return p.module(tier,self.rng,level=level)
  names=[n for n,v in r.GEAR.items() if v[0]==category and p.GEAR_MIN_LEVEL[n]<=level]
  item=p.equipment(self.rng.choice(names),tier,self.rng,level)
  if self.rng.random()<.08:
   target='weapon' if category=='weapon' else 'protection';pool=[n for n,m in enumerate(r.MODULES) if m[1]==target]
   for _ in range(min(item['slots'],1+(self.rng.random()<.04))):item['modules'].append(p.module(tier,self.rng,self.rng.choice(pool),level))
  p.mr.clamp_condition(item)
  return item
 def monster_loot_level(self,kills,fallback=1):
  """Обчислює допустимий рівень здобичі за переможених монстрів."""
  source=self.rng.choice(kills) if kills else {}
  level=max(1,int(source.get('level',fallback)))
  return self.rng.randint(max(1,level-2),level)
 def start_battle(self):
  """Створює бойовий стан, ворогів та арену поточної зустрічі."""
  super().start_battle();self.battle['kills']=[]
 def victory(self):
  """Завершує переможний бій і нараховує його результати."""
  if not self.battle:return
  b=self.battle;self._last_battle=copy.deepcopy(b);kills=[e for e in b.get('kills',[]) if not e.get('human')]
  chance,rolls,cap=loot_rules(kills)
  human_only=(bool(b.get('kills')) and not kills) or (b.get('safe_exit047') and not b.get('kills'))
  if human_only:rolls=0
  self.battle=None;qid=self.quest_battle;self.quest_battle=None
  credits=round(self.rng.randint(40,65)*(1+.35*(b.get('region_level',1)-1))*(1+.15*self.rank('scavenger')));credits=0 if human_only else credits;self.money+=credits
  before_loot={i['id']:i.get('qty',1) for i in self.loot}
  drops=0
  for _ in range(rolls):
   if self.rng.random()<chance:
    item=self.reward_item(cap,level=self.monster_loot_level(kills,b.get('region_level',1)))
    if 'durability' in item and self.rng.random()<.95:item['durability']=self.rng.randint(10,95)
    p.add_to(self.loot,item);drops+=1
  # Independent supplies. They never replace successful equipment rolls.
  for _ in range(0 if human_only else 2):
   if self.rng.random()<.20:p.add_to(self.loot,p.ammunition(self.rng.choice(list(p.AMMO)),max(1,self.rng.randint(3,12)//2)))
  for kind,prob in [('food',.20),('med',.12),('rad',.05)]:
   if not human_only and self.rng.random()<prob:p.add_to(self.loot,p.supply(kind))
  for fn in (p.parts,p.fragments):
   if not human_only and self.rng.random()<.35:p.add_to(self.loot,fn(self.rng.randint(2,8)))
  for e in kills:
   if self.rng.random()<.65:p.add_to(self.loot,trophy(e['kind']))
  for item in b.get('faction_loot',[]):p.add_to(self.loot,item)
  for item in b.get('mythic_bonus',[]):p.add_to(self.loot,item)
  if getattr(self,'coward_turns',0):
   from loot032 import halve_new_loot
   halve_new_loot(self,before_loot)
   penalty=credits-credits//2;self.money-=penalty;credits-=penalty
  if qid:
   q=next((q for q in self.quests if q['id']==qid and q['status']=='active'),None)
   if q:q['progress']=1;self.emit(tr('economy.0004'),color='#c7a0f1')
  self.log(tr('economy.0005', v0=credits, v1=rolls, v2=chance, v3=drops))
 def price_quest(self,q):
  """Розраховує винагороду завдання з урахуванням його рівня."""
  zone=q.get('level',q.get('zone',self.region_at(*self.cities[q['city']])))
  multiplier=2 if q.get('unique') else 1
  fee=round(BASE_REWARDS[q['kind']]*zone**1.3*multiplier)
  compensation=0
  if q['kind']=='supplies':compensation=round(18*1.15)*q.get('food_need',5 if q.get('unique') else 3)+round(42*1.15)*q.get('med_need',3 if q.get('unique') else 2)
  if q['kind']=='trophies':compensation=3*trophy(q['target_kind'])['value']*q['goal']
  q.update(reward=fee+compensation,economy_scaled=True,zone=zone,level=zone,xp_reward=(25+5*(zone-1))*multiplier)
 def mayor_offers(self):
  """Повертає актуальний список доступних завдань квестодавця."""
  offers=super().mayor_offers()
  if not offers:return offers
  if not any(q['kind']=='trophies' for q in offers):
   kind=self.rng.randrange(min(12,5+self.region_level))
   offers.append(dict(id=r.uid(),kind='trophies',city=self.city,status='offered',title=tr('economy.0006'),progress=0,goal=3+(self.region_level-1)//2,target_kind=kind,reward=0,pos=None,zone=self.region_level,unique=self.rng.random()<.18,scaled=True,distance_scaled=True,cycle_named=True))
  for q in offers:
   if q['status']=='offered' and not q.get('economy_scaled'):self.price_quest(q)
  return offers
 def quest_ready(self,q):
  """Перевіряє виконання всіх умов для здачі завдання."""
  if q['kind']=='trophies':return q['status']=='active' and self.trophy_count(q['target_kind'])>=q['goal']
  return super().quest_ready(q)
 def quest_text(self,q):
  """Формує опис цілі, прогресу й винагороди завдання."""
  if q['kind']=='trophies':
   text=tr('economy.0007', v0=q['title'], v1=BODY_NAMES[q['target_kind']], v2=self.trophy_count(q['target_kind']), v3=q['goal'], v4=self.city_name(q['city']), v5=q['reward'], v6=80 if q.get('unique') else 40)
  else:text=super().quest_text(q)
  text=text.replace(f'{80 if q.get("unique") else 40} XP',f'{q.get("xp_reward",80 if q.get("unique") else 40)} XP')
  text=tr('economy.0008', v0=q.get('level', q.get('zone', 1)))+text
  if q.get('unique'):text+=tr('economy.0009')
  return text
 def turn_in(self,quest_id):
  """Перевіряє умови здачі, видає нагороду й завершує завдання."""
  q=next((q for q in self.quests if q['id']==quest_id),None)
  ok=super().turn_in(quest_id)
  if ok:
   if q['kind']=='trophies':self.consume_trophies(q['target_kind'],q['goal'])
   if q.get('unique'):
    if hasattr(self,'give_quest_items'):self.give_quest_items(q)
    else:
     for _ in range(1+(self.rng.random()<.10)):
      item=self.reward_item(4,1,level=q.get('level',q.get('zone',1)))
      if not self.accept(item):p.add_to(self.stash,item)
  return ok
 @classmethod
 def load(cls,path):
  """Завантажує збереження та застосовує міграції цієї версії."""
  version=json.loads(Path(path).read_text(encoding='utf-8'))['version'];game=super().load(path);game.add_hunters()
  if version<7:
   def reprice(item):
    if item['kind'] in ('weapon','armor','helmet'):item['value']=round((70+item['weight']*15)*item.get('level',1)**1.3*[1,1.8,3.5,7,14][item['rarity']])
    elif item['kind']=='module':item['value']=round(30*(item['rarity']+1)**2*item.get('level',1)**1.3)
    if 'sealed_price' in item:item['sealed_price']=round(85*game.level**1.3)
    for m in item.get('modules',[]):reprice(m)
   items=game.bag+game.loot+game.stash+[i for i in game.equipped.values() if i]
   for entry in game.shops.values():items+=entry['items']
   if game.traveler:items+=game.traveler['items']
   for item in items:reprice(item)
   # Existing accepted contracts retain their promised credit reward.
   for q in game.quests:q['economy_scaled']=True
   game.offers={};game.offer_refresh={}
  if game.battle and 'kills' not in game.battle:game.battle['kills']=[dict(kind=e['kind'],grade=e.get('grade','normal')) for e in game.battle.get('corpses',[])]
  return game
