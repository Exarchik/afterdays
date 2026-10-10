"""Presentation snapshots; never apply rewards a second time."""
import copy


def groups(report):
    states=[];items=[]
    for row in report['rows']:
        (items if row.get('item') and row.get('destination') else states).append(row)
    return states,items


def snapshot(game):
    return {place:{i['id']:i.get('qty',1) for i in getattr(game,place)}
            for place in ('bag','loot','stash')}


def finish(game, title, art, start, before=None):
    rows=[]
    for event in game._events[start:]:
        if event['kind']=='text' and event.get('text'):
            rows.append(copy.deepcopy(event))
    if before is not None:
        for place in ('bag','loot','stash'):
            for item in getattr(game,place):
                qty=item.get('qty',1)-before[place].get(item['id'],0)
                if qty>0:
                    view=copy.deepcopy(item);view['qty']=qty
                    rows.append(dict(text=f'+{qty} {item["name"]}',item=view,
                                     destination=place,color='#9cdda8'))
    report=dict(title=title,art=art,rows=rows,pos=[game.x,game.y])
    if not hasattr(game,'_event_results'):game._event_results=[]
    game._event_results.append(report)
    return report


def decorate(events,kind):
    """Attach semantic icons without parsing translated result strings."""
    for event in events:
        if event['kind']=='text':event.setdefault('effect_kind',kind)
