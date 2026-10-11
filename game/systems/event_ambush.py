"""Authored event encounters use ordinary combat actors and arena placement."""
import content
import faction_rules
import monster_rules


def populate(game,effect):
    doc=faction_rules.catalog();b=game.battle;level=b.get('region_level',game.region_level)
    count=effect.get('amount',1);monster=effect.get('monster_id')
    if monster:
        faction=next((key for key,d in doc['factions'].items() if monster in d['members']),'monsters')
        roster=[(faction,monster)]*count
    else:
        keys=[key for key,d in doc['factions'].items() if d['members']] if effect['faction']=='mixed' else [effect['faction']]
        game.rng.shuffle(keys)
        roster=[]
        for n in range(count):
            faction=keys[n%len(keys)]
            members=doc['factions'][faction]['members']
            eligible=[key for key in members if (doc['humans'][key]['min_level']<=level if key in doc['humans'] else content.MONSTER_DATA[key]['base_level']<=level+1)]
            roster.append((faction,game.rng.choice(eligible or members)))
    actors=[]
    for faction,ident in roster:
        actor=(faction_rules.make_human(game.rng,ident,faction,level,[0,0],doc) if ident in doc['humans'] else
               monster_rules.make(game.rng,ident,level,[0,0]))
        actor.update(faction=faction,ambush_hostile=True,awake=True,sight=5)
        actors.append(actor)
    b['enemies']=actors
    from arena_layout import build
    build(game)
