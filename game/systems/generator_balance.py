"""Generator repair: balance switches with different (some negative) loads into a green zone.

Each switch adds its own load to the gauge; one or more switches take load away. The green
zone is placed around the sum of a random set of switches. Going over the red line trips
the protection and switches everything off. Everything is deterministic from the quest ID.
"""
import random

KIND='generator'
VERSION=2
RED=100     # protection trips above this load
MAX=120     # gauge scale
# Editor-tunable settings: (default, minimum, maximum).
SETTINGS={'switches':(5,3,7),'negatives':(2,0,3),'zone':(5,2,10),'show_weights':(0,0,1),
          'shock_chance':(35,0,100),'shock_max':(5,0,5)}


def settings_for(spec):
    spec=spec or {}
    return {key:spec.get(key,default) for key,(default,_,_) in SETTINGS.items()}


def validate_settings(spec,prefix=''):
    errors=[f'{prefix}Некоректне поле {key}: ціле число від {low} до {high}'
            for key,(_,low,high) in SETTINGS.items()
            if key in spec and (type(spec[key]) is not int or not low<=spec[key]<=high)]
    values=settings_for(spec)
    if not errors and values['negatives']>=values['switches']:
        errors.append(f'{prefix}Від’ємних рубильників має бути менше, ніж усіх')
    return errors


def subset_sums(weights):
    """(mask, sum) of every non-empty set of switches."""
    n=len(weights)
    return [(mask,sum(w for i,w in enumerate(weights) if mask>>i&1)) for mask in range(1,1<<n)]


def generate(rng,settings):
    """Weights and green zone. Strict rules first, relaxed only if a small board cannot satisfy them."""
    n=settings['switches'];half=settings['zone']
    negatives=min(settings['negatives'],n-1)
    for attempt in range(4000):
        strict=attempt<3000
        count=rng.randint(min(1,negatives),negatives) if negatives else 0
        weights=[]
        for _ in range(400):
            if len(weights)>=n:break
            minus=len(weights)<count
            value=-rng.randint(8,25) if minus else rng.randint(12,45)
            if all(abs(value-w)>=4 for w in weights):weights.append(value)
        if len(weights)<n:continue
        rng.shuffle(weights)
        if strict and sum(w for w in weights if w>0)<=RED+5:continue
        size=rng.randint(2,min(4,n));chosen=rng.sample(range(n),size)
        if strict and count and not any(weights[i]<0 for i in chosen):continue
        center=sum(weights[i] for i in chosen)
        if not 25<=center<=RED-half-10:continue
        hits=[(mask,total) for mask,total in subset_sums(weights) if abs(total-center)<=half]
        positive_only=any(all(not mask>>i&1 or w>0 for i,w in enumerate(weights)) for mask,_ in hits)
        # Bigger boards have many more sets, so a few more of them may land in the zone.
        if strict and (len(hits)>max(2,n-3) or (count and positive_only)):continue
        return weights,[center-half,center+half]
    # Fallback that always works: a plain board where two switches make the zone.
    weights=[20+7*i for i in range(n)];center=weights[0]+weights[1]
    return weights,[center-half,center+half]


def load(q):
    return sum(w for w,on in zip(q['generator_weights'],q['generator_on']) if on)


def in_zone(q):
    lo,hi=q['generator_zone']
    return lo<=load(q)<=hi
