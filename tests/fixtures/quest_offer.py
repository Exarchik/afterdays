"""Select a deterministic board entry for tests of quest mechanics, not generation."""
def offer_for(game, kind, unique=False):
    game.local_record()['value']=75
    game.mayor_offers()
    key=str(game.city)
    q=next(q for q in game.offers[key] if q['kind']==kind and q['status']=='offered')
    q['rep_elite_roll']=0 if unique else 1
    board=game.reputation_state['boards'][key]
    board['ids']=[q['id']]+[i for i in board['ids'] if i!=q['id']]
    return next(x for x in game.mayor_offers() if x['id']==q['id'])
