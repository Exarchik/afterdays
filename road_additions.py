from i18n import t as tr
"""Twenty optional, terrain-aware road encounters."""
# key, terrain, title, story, action, cost, success chance, success, failure
EVENTS=[
('water_filter','waste',tr('road_additions.0001'),tr('road_additions.0002'),tr('road_additions.0003'),('parts',3),1,[('heal',12)],[]),
('old_survey','road',tr('road_additions.0004'),tr('road_additions.0005'),tr('road_additions.0006'),None,1,[('reveal',2),('xp',15)],[]),
('beehive','forest',tr('road_additions.0007'),tr('road_additions.0008'),tr('road_additions.0009'),None,.65,[('food',2)],[('damage',4)]),
('copper_wire','ruin',tr('road_additions.0010'),tr('road_additions.0011'),tr('road_additions.0012'),None,.75,[('parts',8)],[('damage',5)]),
('scrap_buyer','road',tr('road_additions.0013'),tr('road_additions.0014'),tr('road_additions.0015'),('parts',8),1,[('money',30)],[]),
('plate_buyer','road',tr('road_additions.0016'),tr('road_additions.0017'),tr('road_additions.0018'),('fragments',6),1,[('money',28)],[]),
('lost_dog','forest',tr('road_additions.0019'),tr('road_additions.0020'),tr('road_additions.0021'),('food',1),1,[('parts',5),('xp',20)],[]),
('bunker_light','ruin',tr('road_additions.0022'),tr('road_additions.0023'),tr('road_additions.0024'),('parts',2),1,[('energy',8)],[]),
('clean_spring','forest',tr('road_additions.0025'),tr('road_additions.0026'),tr('road_additions.0027'),None,1,[('heal',10)],[]),
('dust_archive','ruin',tr('road_additions.0028'),tr('road_additions.0029'),tr('road_additions.0030'),None,1,[('xp',25)],[]),
('glass_dune','waste',tr('road_additions.0031'),tr('road_additions.0032'),tr('road_additions.0033'),None,.7,[('fragments',10)],[('damage',4)]),
('buried_battery','waste',tr('road_additions.0034'),tr('road_additions.0035'),tr('road_additions.0036'),None,.6,[('energy',12)],[('damage',6)]),
('field_tailor','road',tr('road_additions.0037'),tr('road_additions.0038'),tr('road_additions.0039'),('money',15),1,[('repair_armor',15)],[]),
('gun_oil','road',tr('road_additions.0040'),tr('road_additions.0041'),tr('road_additions.0042'),('money',12),1,[('repair_weapon',12)],[]),
('locked_locker','ruin',tr('road_additions.0043'),tr('road_additions.0044'),tr('road_additions.0045'),('parts',5),1,[('med',1)],[]),
('warning_flags','waste',tr('road_additions.0046'),tr('road_additions.0047'),tr('road_additions.0048'),None,1,[('rad',1),('xp',10)],[]),
('fallen_tree','forest',tr('road_additions.0049'),tr('road_additions.0050'),tr('road_additions.0051'),None,.7,[('food',1),('parts',4)],[('damage',3)]),
('broken_radio','road',tr('road_additions.0052'),tr('road_additions.0053'),tr('road_additions.0054'),('parts',4),1,[('money',25),('reveal',2)],[]),
('cemetery','waste',tr('road_additions.0055'),tr('road_additions.0056'),tr('road_additions.0057'),None,1,[('xp',15),('reveal',1)],[]),
('roof_cache','ruin',tr('road_additions.0058'),tr('road_additions.0059'),tr('road_additions.0060'),None,.65,[('money',45),('med',1)],[('damage',6)]),
]
import content
for row in content.read('road_events032.json'):
    for index in (2,3,4):row[index]=tr(row[index])
    EVENTS.append(row)
BY_KEY={e[0]:e for e in EVENTS}

def resolve(game,choice):
    import progression as p
    spec=BY_KEY[game.road_event['kind']]
    if choice=='leave':game.road_event=None;game.log(tr('road_additions.0061'));return True
    if choice!='act':return False
    cost=spec[5]
    if cost:
        kind,n=cost
        if (game.money if kind=='money' else game.count(kind))<n:game.log(tr('road_additions.0062'));return False
    if any(k=='repair_armor' for k,n in spec[7]) and not game.equipped.get('armor'):game.log(tr('road_additions.0063'));return False
    if any(k=='repair_weapon' for k,n in spec[7]) and not game.weapon:game.log(tr('road_additions.0064'));return False
    if cost:
        if cost[0]=='money':game.money-=cost[1]
        else:game.consume(*cost)
    game.road_event=None
    effects=spec[7] if game.rng.random()<spec[6] else spec[8]
    for kind,n in effects:
        if kind=='damage':game.hurt_world(n,spec[2])
        elif kind=='money':game.money+=n;game.emit(tr('road_additions.0065', v0=n))
        elif kind=='xp':game.gain_xp(n)
        elif kind=='heal':
            before=game.hp;game.hp=min(game.max_hp,game.hp+n);game.emit(f'+{game.hp-before} HP')
        elif kind=='reveal':game.reveal(game.x,game.y,n);game.emit(tr('road_additions.0066'))
        elif kind.startswith('repair_'):
            item=game.weapon if kind=='repair_weapon' else game.equipped['armor'];item['durability']=min(__import__('module_rules').max_condition(item),__import__('module_rules').condition(item)+n);game.emit(tr('road_additions.0067'))
        else:
            item=p.parts(n) if kind=='parts' else p.fragments(n) if kind=='fragments' else p.ammunition('energy',n) if kind=='energy' else p.supply(kind,n)
            p.add_to(game.loot,item);game.emit(tr('road_additions.0068'))
    game.log(tr('road_additions.0069')+spec[2]+'.');return True
