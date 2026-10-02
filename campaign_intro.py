"""New-game placement and the first campaign's two-step radio trigger."""
STORY_ID='noise_in_the_wind'


def prepare(game):
    if 'campaign_intro' in game.reputation_state:return
    # A safe clearing with one road through the start, turning toward the town.
    cells={(x,y) for y in range(4) for x in range(4)}
    cx,cy=game.cities[0]
    road={(x,1) for x in range(cx+1)}
    road.update((cx,y) for y in range(1,cy+1))
    cells.update(road)
    protected={tuple(p) for p in game.cities}|{tuple(s['pos']) for s in game.special_sites}
    for x,y in cells:
        if (x,y) not in protected:game.world[y][x]='road' if (x,y) in road else 'waste'
        game.radiation.pop(f'{x},{y}',None)
    game.x=game.y=1
    game.explored=[];game.known_cities=[];game.reveal(1,1,2)
    game.reputation_state['campaign_intro']=dict(moves=0)


def pending(game):
    if game.battle or game.road_event:return None
    state=game.story_states().get(STORY_ID)
    if state and state['status']=='active' and state['definition']['stages'][state['index']]['kind']=='dialogue':return STORY_ID
    return None
