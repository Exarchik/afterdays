"""Apply catalog choices using existing game inventory, map and lock mechanics."""
import copy
import event_catalog as catalog

def make(game, key=None):
    if game.battle or game.road_event: return False
    if key is not None:
        spec = catalog.BY_ID.get(key)
    else:
        pool = [e for e in catalog.EVENTS if e['enabled'] and e['terrain'] in ('any', game.world[game.y][game.x])]
        if not pool: return False
        spec = game.rng.choices(pool, weights=[e['weight'] for e in pool])[0]
    if not spec or not spec['enabled']: return False
    # Snapshot rules as well as text: editing the catalog cannot alter an active save's choice.
    game.road_event = dict(kind=spec['id'], title=spec['title'], body=spec['description'], art=spec['art'],
                           choices=[[c['id'], c['text']] for c in spec['choices']],
                           pos=[game.x, game.y], definition=copy.deepcopy(spec))
    game.last_event_turn = game.turn; game.log(spec['title'])
    return True

def display_choices(event):
    """Use authored labels, including saves made with generated effect summaries."""
    spec = event.get('definition') or catalog.BY_ID.get(event['kind'], {})
    labels = {choice['id']: choice['text'] for choice in spec.get('choices', [])}
    return [(key, labels.get(key, label)) for key, label in event['choices']]

def item(game, effect, level):
    import progression as p
    kind = effect['kind']
    if kind == 'gear':
        gear = game.reward_item(cap=min(3, 1+level//4), level=game.rng.randint(max(1, level-2), level))
        if 'durability' in gear: gear['durability'] = float(game.rng.randint(30, 90))
        return gear
    n = catalog.amount(effect, level, game.rng)
    if kind == 'money':return p.supply('credits',n)
    if kind in ('food','med','rad','repairkit'):
        import content
        ident=effect.get('item_id','item_'+kind)
        if ident=='random':ident=game.rng.choice([key for key,d in content.CONSUMABLES.items() if d['kind']==kind])
        if content.CONSUMABLES.get(ident,{}).get('kind')!=kind:raise ValueError('Невідомий предмет події: '+ident)
        return p.supply(ident,n)
    if kind == 'ammo':
        ammo = effect.get('ammo', 'random')
        if ammo == 'random': ammo = game.rng.choice(list(p.AMMO))
        return p.ammunition(ammo, n)
    return p.parts(n) if kind == 'parts' else p.fragments(n) if kind == 'fragments' else p.supply(kind, n)

def cache_contents(game, effects, level):
    return [item(game, e, level) for e in effects if e.get('chance', 1) >= 1 or game.rng.random() < e['chance']]

def grant_item(game, effect, reward):
    """Announce direct inventory rewards, including additions to an existing stack."""
    import progression as p
    destination=effect.get('destination','loot')
    quantity=reward.get('qty',1)
    name=reward['name']
    p.add_to(getattr(game,destination),reward)
    suffix=' (здобич)' if destination=='loot' else ' (сховище)' if destination=='stash' else ''
    game.emit(f'+{quantity} {name}'+suffix,color='#9cdda8')


def apply(game, effect, spec):
    previous=getattr(game,'_event_feedback_color',None)
    negative=effect['kind'] in ('damage','radiation','satiety_loss','wear','wear_armor') or effect.get('amount',0)<0
    game._event_feedback_color='#e56860' if negative else '#9cdda8'
    try:return _apply(game,effect,spec)
    finally:game._event_feedback_color=previous


def _apply(game, effect, spec):
    import progression as p
    import module_rules
    kind = effect['kind']; level = game.region_level
    if effect.get('chance', 1) < 1 and game.rng.random() >= effect['chance']: return
    if kind == 'cache':
        game.begin_event_cache(spec); return
    if kind == 'gear':
        grant_item(game, effect, item(game, effect, level)); return
    n = catalog.amount(effect, level, game.rng)
    if kind in catalog.ITEM_KINDS:
        if n < 0:
            if kind in ('food','med','rad','repairkit') and effect.get('item_id'):
                import content
                ident=effect['item_id'];pool=[i for i in game.bag if i['kind']==kind and not i.get('quest_id') and (ident=='random' or i.get('type_id','item_'+kind)==ident)]
                if ident=='random':game.rng.shuffle(pool)
                remaining=-n
                for owned in pool:
                    count=min(remaining,owned.get('qty',1));p.extract(game.bag,owned,count);remaining-=count
                    if count:game.emit(f"−{count} {owned['name']}")
                    if not remaining:break
                return
            ammo = effect.get('ammo', 'random')
            if kind == 'ammo' and ammo == 'random': ammo = game.rng.choice(list(p.AMMO))
            removed=min(game.count('ammo',ammo) if kind=='ammo' else game.count(kind),-n)
            if kind == 'ammo': game.consume('ammo',removed,ammo)
            else: game.consume(kind,removed)
            if removed:game.emit(f'−{removed} '+(p.AMMO[ammo][0] if kind=='ammo' else catalog.EFFECTS[kind][0]))
        elif n:
            resolved = dict(effect, amount=n, per_level=0, step=0); resolved.pop('maximum', None)
            grant_item(game, effect, item(game, resolved, level))
        return
    if kind == 'money':
        before=game.money;game.money=max(0,game.money+n)
        if game.money!=before:game.emit(f'{game.money-before:+g} кредитів')
    elif kind == 'xp': game.gain_xp(n)
    elif kind == 'heal':
        before=game.hp;game.hp=min(game.max_hp,game.hp+n)
        if game.hp!=before:game.emit(f'{game.hp-before:+g} HP')
    elif kind == 'damage': return game.hurt_world(n, spec['title'])
    elif kind == 'radiation': return game.add_radiation(n)
    elif kind == 'radiation_heal': game.cure_radiation(n)
    elif kind in ('satiety_gain','satiety_loss'): return game.change_satiety(n if kind=='satiety_gain' else -n)
    elif kind in catalog.TIMED_EFFECTS: game.add_buff(kind,effect['duration'],n)
    elif kind == 'wear_armor':
        armor=game.equipped.get('armor')
        if armor:
            before=module_rules.condition(armor);game.wear(armor,n)
            if before!=module_rules.condition(armor):game.emit(f'Стан броні −{before-module_rules.condition(armor):g}',color='#e56860')
    elif kind == 'wear':
        if game.weapon:
            before=module_rules.condition(game.weapon);game.wear(game.weapon,n)
            if before!=module_rules.condition(game.weapon):game.emit(f'Стан зброї −{before-module_rules.condition(game.weapon):g}')
    elif kind == 'reveal':
        game.reveal(game.x,game.y,n)
    elif kind == 'discover':
        if not game.discover(): game.gain_xp(n)
    elif kind.startswith('repair_'):
        gear = game.weapon if kind == 'repair_weapon' else game.equipped.get('armor')
        if gear:
            before=module_rules.condition(gear);gear['durability']=min(module_rules.max_condition(gear),before+n)
            if gear['durability']!=before:game.emit(f"Стан {'зброї' if kind=='repair_weapon' else 'броні'} +{gear['durability']-before:g}")

def resolve(game, choice_id):
    event = game.road_event
    if not event: return False
    spec = event.get('definition') or catalog.BY_ID.get(event['kind'])
    if not spec: game.log('Ця подія відсутня в каталозі.'); return False
    choice = next((c for c in spec['choices'] if c['id'] == choice_id), None)
    if not choice: return False
    # Sum repeated costs before checking to prevent partial payment.
    costs = {}
    for cost in choice.get('costs', []): costs[cost['kind']] = costs.get(cost['kind'], 0)+cost['amount']
    for kind, n in costs.items():
        if (game.money if kind == 'money' else game.count(kind)) < n:
            game.log('Недостатньо ресурсів для цієї дії.'); return False
    kinds = {e['kind'] for o in choice['outcomes'] if o['chance'] > 0 for e in o['effects']}
    if 'repair_weapon' in kinds and not game.weapon:
        game.log('Спочатку екіпіруйте зброю.'); return False
    if 'repair_armor' in kinds and not game.equipped.get('armor'):
        game.log('Спочатку вдягніть броню.'); return False
    for kind, n in costs.items():
        if kind == 'money': game.money -= n
        else: game.consume(kind, n)
        text=f'−{n} '+catalog.EFFECTS[kind][0]
        game.log(text,color='#e56860');game.emit(text,color='#e56860')
    outcomes = choice['outcomes']; selected = outcomes[0]
    if len(outcomes) > 1:
        roll = game.rng.random(); cumulative = 0
        for outcome in outcomes:
            cumulative += outcome['chance']
            if roll < cumulative: selected = outcome; break
    game.road_event = None
    for effect in selected['effects']:
        # defeat() restores HP, so use hurt_world's result to stop after lethal damage.
        if apply(game, effect, spec) is False: break
    game.log('Подія завершена: '+spec['title']+'.')
    return True
