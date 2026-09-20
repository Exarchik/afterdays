import hexgrid
from i18n import t as tr
"""Location markets, cartographers and room-based dungeon expeditions."""
import exploration
import balance
import copy
import json
import math
from pathlib import Path
import afterdays as r
import progression as p
import adventure as a
import economy

METRO_CITIES=(0,2,3,7,10)
METRO_PARTS={2:tr('frontier.0001'),3:tr('frontier.0002'),7:tr('frontier.0003'),10:tr('settlements.metro_part')}

DUNGEONS=(tr('frontier.0004'),tr('frontier.0005'),tr('frontier.0006'))

class Game(economy.Game):
    @property
    def cartographer(self):
        return bool(not self.battle and self.traveler and self.traveler.get('cartographer') and self.traveler['pos']==[self.x,self.y])

    def available_merchant(self,m):
        if self.cartographer and m in (3,4):return False
        return super().available_merchant(m)

    def spawn_traveler(self):
        if self.rng.random()<.20:self.spawn_cartographer()
        else:super().spawn_traveler()

    def spawn_cartographer(self):
        size=self.rng.randint(3,6)
        boxes=[(x,y) for y in range(max(0,self.y-size),min(32-size,self.y+size)+1)
               for x in range(max(0,self.x-size),min(48-size,self.x+size)+1)
               if any(not self.revealed(xx,yy) for yy in range(y,y+size) for xx in range(x,x+size))]
        if not boxes:return False
        x,y=self.rng.choice(boxes)
        self.traveler=dict(cartographer=True,pos=[self.x,self.y],items=[],box=[x,y,size],price=10+3*size,purchased=False)
        self.last_traveler_turn=self.turn
        self.log(tr('frontier.0007', v0=size, v1=size, v2=10 + 3 * size))
        return True

    def buy_map(self):
        if not self.cartographer or self.traveler['purchased']:return False
        t=self.traveler;x,y,size=t['box']
        cells={f'{xx},{yy}' for yy in range(y,y+size) for xx in range(x,x+size)}
        if not cells-set(self.explored):self.log(tr('frontier.0008'));return False
        if self.money<t['price']:self.log(tr('frontier.0009'));return False
        self.money-=t['price'];t['purchased']=True
        self.explored=sorted(set(self.explored)|cells)
        for n,pos in enumerate(self.cities):
            if self.revealed(*pos) and n not in self.known_cities:self.known_cities.append(n)
        self.log(tr('frontier.0010', v0=size, v1=size));return True

    def name_dungeon(self,q):
        if q['kind']=='purge':
            if 'dungeon_kind' not in q:q['dungeon_kind']=self.rng.choice(DUNGEONS)
            q['title']=(tr('frontier.0011') if q.get('unique') else tr('frontier.0012'))+q['dungeon_kind']

    def mayor_offers(self):
        offers=super().mayor_offers()
        for q in offers:
            self.name_dungeon(q)
            if 'level' not in q:self.price_quest(q)
        city=self.city
        if not self.battle and city in METRO_CITIES[1:] and not any(q.get('metro_city')==city for q in self.quests):
            if not any(q.get('metro_city')==city for q in offers):
                q=dict(id=r.uid(),kind='retrieve',city=city,status='offered',title=tr('frontier.0013'),
                       progress=0,goal=1,target_kind=None,reward=0,pos=None,unique=True,metro_city=city,
                       part_name=METRO_PARTS[city],zone=self.region_level,scaled=True,distance_scaled=True,cycle_named=True)
                self.price_quest(q);offers.append(q)
        for q in offers:
            if q['kind'] in ('hunt','trophies') and not q.get('count_balanced'):
                q['goal']=exploration.objective_count(self.rng,q.get('target_kind'));q['count_balanced']=True;self.price_quest(q)
        return offers

    def stock(self,merchant):
        items=super().stock(merchant)
        if merchant==2:
            for n,item in enumerate(items):
                if item['kind'] in ('sealed','repairkit'):continue
                price=item.get('sealed_price',round(85*self.region_level**1.3))
                items[n]=dict(id=r.uid(),type_id='item_sealed',kind='sealed',name=tr('frontier.0014'),rarity=0,level=item.get('level',1),
                              weight=p.item_weight(item),value=price,sealed_price=price,contents=item)
        return items

    def buys_kind(self,item,merchant):
        if item['kind']=='sealed':return False
        return super().buys_kind(item,merchant)

    def open_chest(self,item_id):
        if self.battle:return None
        chest=next((i for i in self.bag if i['id']==item_id and i['kind']=='sealed'),None)
        if not chest or not chest.get('contents'):return None
        item=chest['contents']
        if self.weight-p.item_weight(chest)+p.item_weight(item)>self.capacity+.0001:return None
        self.bag.remove(chest);p.add_to(self.bag,item)
        self.log(tr('frontier.0015')+item['name']);return item

    def ordinary_search(self):
        pos=[self.x,self.y]
        if pos in self.searched:self.log(tr('frontier.0016'));return False
        self.searched.append(pos);self.turn+=1;self.rad_turns=max(0,self.rad_turns-1)
        if self.rng.random()<.04:
            if self.rng.random()<.10:
                level=self.region_level;item=self.reward_item(min(4,level//3),level=level)
            else:
                kind=self.rng.choice(['food','med','rad','ammo','parts','fragments'])
                item=p.ammunition(self.rng.choice(list(p.AMMO)),self.rng.randint(3,10)) if kind=='ammo' else p.parts(self.rng.randint(2,6)) if kind=='parts' else p.fragments(self.rng.randint(2,6)) if kind=='fragments' else p.supply(kind)
            p.add_to(self.loot,item);self.log(tr('frontier.0017')+item['name']+tr('frontier.0018'))
        else:self.log(tr('frontier.0019'))
        if self.rng.random()<.35:self.start_battle()
        return True

    @property
    def metro_unlocked(self):
        return [city for city in METRO_CITIES if city==0 or any(q.get('metro_city')==city and q['status']=='done' for q in self.quests)]

    def metro_cost(self,destination):
        if self.battle or self.city not in self.metro_unlocked or destination not in self.metro_unlocked or destination==self.city:return None
        blocked={(x,y) for y in range(32) for x in range(48) if not self.passable(x,y)}
        from metro_routes import station_order
        order=station_order(self)
        first,last=sorted((order.index(self.city),order.index(destination)))
        stations=order[first:last+1];distance=0
        for a,b in zip(stations,stations[1:]):
            route=r.path_to(tuple(self.cities[a]),tuple(self.cities[b]),48,32,blocked)
            if not route:return None
            distance+=len(route)
        return (50,max(1,math.ceil(distance/5)),distance)

    def metro_travel(self,destination):
        if self.road_event:return False
        cost=self.metro_cost(destination)
        if cost is None:self.log(tr('frontier.0020'));return False
        fare,turns,_=cost
        if self.money<fare:self.log(tr('frontier.0021'));return False
        self.money-=fare;self.turn+=turns;self.rad_turns=max(0,self.rad_turns-turns)
        self.x,self.y=self.cities[destination];self.traveler=None
        self.reveal(self.x,self.y,2);self._visit_objectives()
        self.log(tr('frontier.0022', v0=self.city_name(destination), v1=turns));return True

    def turn_in(self,quest_id):
        q=next((q for q in self.quests if q['id']==quest_id),None)
        ok=super().turn_in(quest_id)
        if ok and q.get('metro_city') in METRO_CITIES:
            self.log(tr('frontier.0023'))
        return ok

    def quest_text(self,q):
        text=super().quest_text(q)
        if 'metro_city' in q:
            text=text.replace(tr('frontier.0024'),tr('frontier.0025', v0=q['part_name']))
            text+=tr('frontier.0026')
        if q['kind']=='purge':
            text=text.replace(tr('frontier.0027'),
                tr('frontier.0028'))
        return text

    def search(self):
        b=self.battle
        if b and b.get('dungeon'):
            if not b['cleared']:self.log(tr('frontier.0029'));return False
            if math.dist(b['pos'],b['chest'])<=1.5:
                if b['chest_open']:self.log(tr('frontier.0030'));return False
                b['chest_open']=True
                cap=economy.loot_rules(b['kills'])[2]
                for _ in range(2):p.add_to(self.loot,self.reward_item(cap,level=self.monster_loot_level(b.get('kills',[]),b.get('region_level',1))))
                for _ in range(2):p.add_to(self.loot,p.ammunition(self.rng.choice(list(p.AMMO)),self.rng.randint(8,20)))
                p.add_to(self.loot,p.supply('med',2));p.add_to(self.loot,p.supply('food',2))
                self.log(tr('frontier.0031'));return True
            if b['pos']==b['exit']:super().victory();return True
            self.log(tr('frontier.0032'));return False
        if not b and not self.road_event:
            q=next((q for q in self.quests if q['kind']=='purge' and q['status']=='active' and not q.get('progress') and q.get('pos')==[self.x,self.y]),None)
            if q:self.start_dungeon(q);return True
        quest_here=any(q['status']=='active' and q['kind'] in ('retrieve','purge') and q.get('pos')==[self.x,self.y] and not self.quest_ready(q) for q in self.quests)
        if not b and self.city is None and not self.road_event and not quest_here:return self.ordinary_search()
        ok=super().search()
        if ok:
            for item in self.bag:
                q=next((q for q in self.quests if q['id']==item.get('quest_id') and 'metro_city' in q),None)
                if q:item['name']=q['part_name']
        return ok

    def start_dungeon(self,q):
        self.name_dungeon(q)
        self.start_battle()
        b=self.battle
        w,h,rooms,floor,entrance,chest=exploration.dungeon_layout(self.rng)
        positions=[pos for pos in sorted(floor) if math.dist(pos,entrance)>7 and list(pos)!=chest]
        zone=q.get('zone',self.region_level)
        enemies=[]
        import monster_rules
        for pos in self.rng.sample(positions,self.rng.randint(6,10)):
            kind=monster_rules.choose(self.rng,self.region_level)
            enemy=monster_rules.make(self.rng,kind,self.region_level,pos,boost=1.35 if q.get('unique') else 1)
            enemy['awake']=False;enemies.append(enemy)
        b.update(w=w,h=h,rooms=rooms,walls=[list((x,y)) for y in range(h) for x in range(w) if (x,y) not in floor],
                 pos=entrance[:],exit=entrance,chest=chest,chest_open=False,cleared=False,dungeon=True,
                 dungeon_kind=q['dungeon_kind'],biome='ruin',enemies=enemies,region_level=zone,kills=[],corpses=[])
        self.quest_battle=q['id'];self.wake_enemies()
        self.log(tr('frontier.0033'))

    def wake_enemies(self,pos=None):
        b=self.battle
        if b and b.get('dungeon'):
            for e in b['enemies']:
                if hexgrid.distance(e['pos'],pos or b['pos'])<=5 and hexgrid.visible(tuple(e['pos']),tuple(pos or b['pos']),b['walls']):e['awake']=True

    def battle_move(self,target):
        b=self.battle
        if not b:return False
        blocked=set(map(tuple,b['walls']))|{tuple(e['pos']) for e in b['enemies']}
        route=hexgrid.path_to(tuple(b['pos']),tuple(target),b['w'],b['h'],blocked) or []
        before=b['pos'][:]
        if b.get('dungeon') and b.get('cleared'):
            if not route:self.log(tr('frontier.0034'));return False
            b['pos']=list(target);ok=True
        else:ok=super().battle_move(target)
        if ok:
            self.emit_move([before]+[list(pos) for pos in route],'player')
            for pos in route:self.wake_enemies(pos)
        return ok

    def shoot(self,enemy_id):
        b=self.battle;e=next((e for e in b['enemies'] if e['id']==enemy_id),None) if b else None
        ok=super().shoot(enemy_id)
        if ok and e:e['awake']=True
        return ok

    def end_turn(self):
        self.wake_enemies();super().end_turn()

    def victory(self):
        if self.battle and self.battle.get('dungeon'):
            if self.battle['enemies']:return
            self.battle['cleared']=True
            self.log(tr('frontier.0035'))
            return
        super().victory()

    def flee(self):
        b=self.battle
        if b and b.get('dungeon'):
            if b['pos']!=b['exit']:self.log(tr('frontier.0036'));return False
            if b['cleared']:super().victory()
            else:self.battle=None;self.quest_battle=None;self.log(tr('frontier.0037'))
            return True
        return super().flee()

    @classmethod
    def load(cls,path):
        version=json.loads(Path(path).read_text(encoding='utf-8'))['version']
        game=super().load(path)
        if version<8:
            game.build_radiation();game.shops={}
            if game.traveler and not game.traveler.get('hunter'):game.traveler=None
        if version<10:
            if version>=3:game.xp=balance.migrate_xp(json.loads(Path(path).read_text(encoding='utf-8'))['xp'])
            def upgrade(item):
                if item['kind']=='weapon':item['stats']['attack']=balance.attack_for(item.get('type_id',item['name']),item.get('level',1))
                elif item['kind'] in ('armor','helmet'):
                    level=item.get('level',1);item['stats']['defense']+=level-1-(level-1)//2
                elif item['kind']=='module' and 'pierce' in item.get('stats',{}):
                    item['stats'].pop('pierce');item['stats']['attack']=item['rarity']+1
                for mod in item.get('modules',[]):upgrade(mod)
            items=game.bag+game.loot+game.stash+[i for i in game.equipped.values() if i]
            for entry in game.shops.values():items+=entry['items']
            if game.traveler:items+=game.traveler.get('items',[])
            seen=set()
            for item in items:
                if item['id'] not in seen:upgrade(item);seen.add(item['id'])
            if game.traveler and not game.traveler.get('hunter') and not game.traveler.get('cartographer'):game.traveler=None
            if game.battle:
                for enemy in game.battle['enemies']:balance.set_monster(enemy)
            for q in game.quests:game.price_quest(q)
            for offers in game.offers.values():
                for q in offers:game.price_quest(q)
        if version<11:
            contracts=list(game.quests)+[q for offers in game.offers.values() for q in offers]
            for q in contracts:
                if q['kind'] in ('hunt','trophies') and q['status']!='done':
                    q['goal']=exploration.objective_count(game.rng,q.get('target_kind'));q['count_balanced']=True
                    q['progress']=min(q.get('progress',0),q['goal']);game.price_quest(q)
        # Repair unfinished destination quests in older saves, keeping rewards and progress.
        for q in game.quests:
            if q['kind'] in ('retrieve','scout','purge','radio') and q['status']=='active' and q.get('pos') and not game.quest_ready(q):
                ceiling=q.get('level',q.get('zone',1))+1
                in_dungeon=game.battle and game.battle.get('dungeon') and game.quest_battle==q['id']
                if not in_dungeon and (game.region_at(*q['pos'])>ceiling or (ceiling>=4 and game.region_at(*q['pos'])<3)):
                    pool=game.quest_locations(q)
                    if pool:q['pos']=list(game.rng.choice(pool))
        for q in game.quests:game.name_dungeon(q)
        for offers in game.offers.values():
            for q in offers:game.name_dungeon(q)
        return game
