"""Disc lock: concentric rings with notches; some rings are geared to a neighbour.

Turning a ring also turns every ring geared to it. The lock opens when every notch is under
the bolt (position 0). Each turn wears the pick; a worn-out pick or a premature open attempt
breaks it (−1 spare part). Layout and start position are deterministic from the lock ID and
the start is always at least a few turns from the solution.
"""
import random
from collections import deque

VERSION=1
# Editor-tunable settings: (default, minimum, maximum).
SETTINGS={'rings':(4,3,5),'positions':(8,6,12),'wear':(10,4,30),'depth':(3,0,6)}


def settings_for(spec):
    spec=spec or {}
    return {key:spec.get(key,default) for key,(default,_,_) in SETTINGS.items()}


def validate_settings(spec,prefix=''):
    return [f'{prefix}Некоректне поле {key}: ціле число від {low} до {high}'
            for key,(_,low,high) in SETTINGS.items()
            if key in spec and (type(spec[key]) is not int or not low<=spec[key]<=high)]


def apply(state,ring,direction):
    """Turn one ring (and the rings geared to it) by one position."""
    k=state['positions'];pos=state['pos']
    pos[ring]=(pos[ring]+direction)%k
    for a,b,d in state['links']:
        if a==ring:pos[b]=(pos[b]+direction*d)%k


def aligned(state):
    return all(v==0 for v in state['pos'])


def distances(state):
    """Fewest turns from every reachable position to the open one (turns are reversible)."""
    n,k=len(state['pos']),state['positions']
    probe=dict(state,pos=[0]*n)
    start=tuple(probe['pos']);dist={start:0};queue=deque([start])
    while queue:
        current=queue.popleft()
        for ring in range(n):
            for direction in (1,-1):
                probe['pos']=list(current);apply(probe,ring,direction);nxt=tuple(probe['pos'])
                if nxt not in dist:dist[nxt]=dist[current]+1;queue.append(nxt)
    return dist


def generate(rng,settings):
    n=settings['rings'];k=settings['positions']
    links=[]
    for i in range(n-1):
        if not links or rng.random()<.7:links.append([i,i+1,1 if rng.random()<.65 else -1])
    if n>=4 and rng.random()<.6:links.append([n-1,n-2,1 if rng.random()<.5 else -1])
    state=dict(version=VERSION,positions=k,links=links,pos=[0]*n,wear=0,wear_max=settings['wear'],turned=0,history=[])
    dist=distances(state)
    want=n+settings['depth']
    far=sorted(p for p,d in dist.items() if want<=d<=want+3)
    pool=far or sorted(p for p,d in dist.items() if d==max(dist.values()))
    state['pos']=list(rng.choice(pool));state['best']=dist[tuple(state['pos'])]
    return state


class DiscLockMixin:
    def lock_settings(self,context):
        """Quest caches follow the native «cache» profile; road caches scale rings with level."""
        if context.get('kind')=='cache':
            import quest_profiles
            spec=quest_profiles.profile(context) or quest_profiles.defaults('cache',bool(context.get('unique')))
            return settings_for(spec)
        level=context.get('level',1)
        return settings_for({'rings':3 if level<=3 else 4 if level<=8 else 5})

    def lock_state(self,context):
        """Disc state of a lock context, created on first use (also for old saves with an angle lock)."""
        state=context.get('lock_disc')
        if not state or state.get('version')!=VERSION:
            state=context['lock_disc']=generate(random.Random('disc-lock:'+str(context['id'])),self.lock_settings(context))
        return state

    def lock_available(self,ident):
        context=self.lock_context(ident)
        if self.battle or not context:return None
        if context.get('kind')=='cache':
            if context.get('lock_open') or not (context.get('lock_found') or 'lock_target' in context):return None
        elif context.get('opened'):return None
        return context

    def lock_turn(self,ident,ring,direction):
        """Turn a ring; wears the pick and breaks it (−1 part) when worn out."""
        self._lock_pick_broke=False
        context=self.lock_available(ident)
        if not context or self.count('parts')<1:return None
        state=self.lock_state(context)
        if type(ring) is not int or not 0<=ring<len(state['pos']) or direction not in (1,-1):return None
        state['history']=(state['history']+[state['pos'][:]])[-30:]
        apply(state,ring,direction);state['turned']+=1;state['wear']+=1
        if state['wear']>=state['wear_max']:
            state['wear']=0;self.consume('parts');self._lock_pick_broke=True
            self.log(tr_worn())
        return True

    def lock_undo(self,ident):
        """Undo the last turn; pick wear stays."""
        context=self.lock_available(ident)
        if not context:return False
        state=self.lock_state(context)
        if not state['history']:return False
        state['pos']=state['history'].pop();return True

    def lock_attempt_failed(self,context):
        """A premature open attempt breaks the current pick."""
        self.consume('parts');self.lock_state(context)['wear']=0


def tr_worn():
    from i18n import t as tr
    return tr('update024.lock_worn')
