"""Persistent combat counters, independent of animation and translated logs."""
import copy


def begin(game,battle=None,*,fresh=False):
    b=battle if battle is not None else game.battle
    if b is None:return None
    if 'result_stats' not in b:
        b['result_stats']=dict(dealt=0,received=0,xp_start=game.xp,rewards=[],reported=False,partial=not fresh)
    return b['result_stats']


def hit(game,kind,amount,hp):
    stats=begin(game)
    if stats is not None:stats[kind]+=max(0,min(amount,max(0,hp)))


def capture_loot(game,battle,before):
    """Record grants at creation, even if supplies were spent or loot later collected."""
    stats=begin(game,battle)
    for item in game.loot:
        qty=item.get('qty',1)-before.get(item['id'],0)
        if qty>0:
            view=copy.deepcopy(item);view['qty']=qty
            stats['rewards'].append(dict(text=f'+{qty} {item["name"]}',item=view,destination='loot',color='#9cdda8'))


def finish(game,battle,outcome):
    if not battle or game.battle is battle:return
    stats=begin(game,battle)
    if stats['reported']:return
    stats['reported']=True
    rows=[dict(text=f'Нанесено шкоди: {stats["dealt"]:g}',effect_kind='damage_dealt',color='#9cdda8'),
          dict(text=f'Отримано шкоди: {stats["received"]:g}',effect_kind='damage',color='#e56860'),
          dict(text=f'Отримано досвіду: {max(0,game.xp-stats["xp_start"]):g} XP',effect_kind='xp',color='#9cdda8')]
    if outcome!='Поразка':rows.extend(copy.deepcopy(stats['rewards']))
    report=dict(title=outcome,art='event_theme:snare',battle=True,partial=stats.get('partial',False),rows=rows,pos=[game.x,game.y])
    if not hasattr(game,'_event_results'):game._event_results=[]
    game._event_results.append(report)
