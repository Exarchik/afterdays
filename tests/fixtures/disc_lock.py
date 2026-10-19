"""Helpers for the disc lock: the shortest sequence of turns, or a direct open for unrelated tests."""
from game.systems import disc_lock


def moves(state):
    """Shortest list of (ring, direction) that opens the lock from its current position."""
    dist=disc_lock.distances(state);probe=dict(state,pos=state['pos'][:]);path=[]
    while not disc_lock.aligned(probe):
        here=dist[tuple(probe['pos'])]
        for ring in range(len(probe['pos'])):
            for direction in (1,-1):
                trial=dict(probe,pos=probe['pos'][:]);disc_lock.apply(trial,ring,direction)
                if dist[tuple(trial['pos'])]==here-1:break
            else:continue
            break
        path.append((ring,direction));probe=trial
    return path


def solve(g,ident):
    """Turn the rings through the real API until every notch is under the bolt."""
    state=g.lock_state(g.lock_available(ident))
    for ring,direction in moves(state):assert g.lock_turn(ident,ring,direction)
    assert disc_lock.aligned(state)


def align(g,ident):
    """Line the lock up without spending pick wear (for tests about cache contents)."""
    state=g.lock_state(g.lock_available(ident));state['pos']=[0]*len(state['pos'])


def open_lock(g,ident):
    align(g,ident);return g.unlock_cache(ident)
