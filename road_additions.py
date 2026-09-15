"""Twenty optional, terrain-aware road encounters."""
# key, terrain, title, story, action, cost, success chance, success, failure
EVENTS=[
('water_filter','waste','Сухий насос','У колодязі вцілів фільтр. Насос потребує кількох деталей.','3 запчастини → +12 HP',('parts',3),1,[('heal',12)],[]),
('old_survey','road','Межовий стовп','Під фарбою збереглася схема місцевості.','Прочитати → карта радіусом 2, +15 XP',None,1,[('reveal',2),('xp',15)],[]),
('beehive','forest','Дикий вулик','Комахи оселились у коробці з консервами.','Ризикнути: 65% на 2 їжі, інакше −4 HP',None,.65,[('food',2)],[('damage',4)]),
('copper_wire','ruin','Мідна проводка','У підвалі звисає пучок старих кабелів.','Зняти: 75% на 8 запчастин, інакше −5 HP',None,.75,[('parts',8)],[('damage',5)]),
('scrap_buyer','road','Збирач брухту','Мандрівник шукає запчастини для печі.','Віддати 8 запчастин → 30 кр.',('parts',8),1,[('money',30)],[]),
('plate_buyer','road','Латки для каравану','Візник ремонтує захист фургона.','Віддати 6 фрагментів → 28 кр.',('fragments',6),1,[('money',28)],[]),
('lost_dog','forest','Собака з жетоном','Пес несе порожню сумку й просить їжі.','Дати їжу → 5 запчастин, +20 XP',('food',1),1,[('parts',5),('xp',20)],[]),
('bunker_light','ruin','Аварійний ліхтар','Під сходами мигає акумулятор.','Витратити 2 запчастини → 8 енергоосередків',('parts',2),1,[('energy',8)],[]),
('clean_spring','forest','Чисте джерело','Вода пройшла крізь товстий шар вапняку.','Відпочити → +10 HP',None,1,[('heal',10)],[]),
('dust_archive','ruin','Польовий щоденник','На сторінках описані місцеві мутанти.','Прочитати → +25 XP',None,1,[('xp',25)],[]),
('glass_dune','waste','Скляна дюна','Пісок спікся в гострі пластини.','Зібрати: 70% на 10 фрагментів, інакше −4 HP',None,.7,[('fragments',10)],[('damage',4)]),
('buried_battery','waste','Заритий акумулятор','З піску стирчать клеми. Корпус може бути під напругою.','Відкрити: 60% на 12 енергоосередків, інакше −6 HP',None,.6,[('energy',12)],[('damage',6)]),
('field_tailor','road','Мандрівна швачка','Майстриня пропонує залатати броню.','Заплатити 15 кр. → броні +15 пунктів стану',('money',15),1,[('repair_armor',15)],[]),
('gun_oil','road','Майстер із мастилом','У механіка залишилось трохи чистого мастила.','Заплатити 12 кр. → зброї +12 пунктів стану',('money',12),1,[('repair_weapon',12)],[]),
('locked_locker','ruin','Медична шафка','Замок цілий, зате петля проіржавіла.','Витратити 5 запчастин → аптечка',('parts',5),1,[('med',1)],[]),
('warning_flags','waste','Жовті прапорці','Хтось позначив небезпечну ділянку й залишив інструкцію.','Вивчити → радіопротектор, +10 XP',None,1,[('rad',1),('xp',10)],[]),
('fallen_tree','forest','Дерево на стежці','Під стовбуром застрягли речі колишнього табору.','Витягти: 70% на їжу й 4 запчастини, інакше −3 HP',None,.7,[('food',1),('parts',4)],[('damage',3)]),
('broken_radio','road','Голос у рації','Оператор просить полагодити передавач.','Витратити 4 запчастини → 25 кр., карта радіусом 2',('parts',4),1,[('money',25),('reveal',2)],[]),
('cemetery','waste','Безіменна могила','На металевій табличці вказані координати старого маршруту.','Занотувати → +15 XP, карта радіусом 1',None,1,[('xp',15),('reveal',1)],[]),
('roof_cache','ruin','Пакунок на даху','Сходи хитаються, але нагорі видно сумку.','Піднятись: 65% на 45 кр. і аптечку, інакше −6 HP',None,.65,[('money',45),('med',1)],[('damage',6)]),
]
BY_KEY={e[0]:e for e in EVENTS}

def resolve(game,choice):
    import progression as p
    spec=BY_KEY[game.road_event['kind']]
    if choice=='leave':game.road_event=None;game.log('Ви продовжили шлях.');return True
    if choice!='act':return False
    cost=spec[5]
    if cost:
        kind,n=cost
        if (game.money if kind=='money' else game.count(kind))<n:game.log('Недостатньо ресурсів для цієї дії.');return False
    if any(k=='repair_armor' for k,n in spec[7]) and not game.equipped.get('armor'):game.log('Спочатку вдягніть броню.');return False
    if any(k=='repair_weapon' for k,n in spec[7]) and not game.weapon:game.log('Спочатку екіпіруйте зброю.');return False
    if cost:
        if cost[0]=='money':game.money-=cost[1]
        else:game.consume(*cost)
    game.road_event=None
    effects=spec[7] if game.rng.random()<spec[6] else spec[8]
    for kind,n in effects:
        if kind=='damage':game.hurt_world(n,spec[2])
        elif kind=='money':game.money+=n;game.emit(f'+{n} кр.')
        elif kind=='xp':game.gain_xp(n)
        elif kind=='heal':
            before=game.hp;game.hp=min(game.max_hp,game.hp+n);game.emit(f'+{game.hp-before} HP')
        elif kind=='reveal':game.reveal(game.x,game.y,n);game.emit('Мапу відкрито')
        elif kind.startswith('repair_'):
            item=game.weapon if kind=='repair_weapon' else game.equipped['armor'];item['durability']=min(100,item['durability']+n);game.emit('Спорядження відремонтовано')
        else:
            item=p.parts(n) if kind=='parts' else p.fragments(n) if kind=='fragments' else p.ammunition('energy',n) if kind=='energy' else p.supply(kind,n)
            p.add_to(game.loot,item);game.emit('Припаси +')
    game.log('Подія завершена: '+spec[2]+'.');return True
