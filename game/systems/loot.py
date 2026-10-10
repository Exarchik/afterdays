"""Retreat penalty only affects newly produced battle loot, never pre-existing inventory."""
def halve_new_loot(game,before):
    for item in list(game.loot):
        old=before.get(item['id'],0);new=max(0,item.get('qty',1)-old)
        kept=sum(game.rng.random()<.5 for _ in range(new))
        if not old+kept:game.loot.remove(item)
        elif 'qty' in item:item['qty']=old+kept
