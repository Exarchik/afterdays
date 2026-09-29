"""Legacy API view. Edit data/road_events.json with event_editor.py."""
import event_catalog

def _legacy(e):
    c=e['choices'][0];outcomes=c['outcomes']
    cost=c.get('costs',[])
    effects=lambda rows:[(x['kind'],x.get('amount',1)) for x in rows]
    return (e['id'],e['terrain'],e['title'],e['description'],c['text'],
            (cost[0]['kind'],cost[0]['amount']) if cost else None,
            outcomes[0]['chance'],effects(outcomes[0]['effects']),
            effects(outcomes[1]['effects']) if len(outcomes)>1 else [])

EVENTS=[_legacy(e) for e in event_catalog.EVENTS if e.get('legacy_group')=='additional']
BY_KEY={e[0]:e for e in EVENTS}

def resolve(game,choice):
    from event_runtime import resolve as apply
    return apply(game,choice)
