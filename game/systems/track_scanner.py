"""Elite hunt: a hand-held track scanner at the first point reveals where the lair is.

The scanner field is a top-down patch of ground with a single hidden group of prints.
Switched off, the lens follows the hand and recharges; switched on, it crawls slowly,
drains charge and reveals prints under the lens. Reading enough prints gives the
direction of travel; the lair is then placed on the world map in that direction.
"""
import math
import random

import world_hex

KIND='elite_hunt'
WIDTH,HEIGHT=900,560
LENS=64
READ_RADIUS=LENS*.6
SIGNAL_RANGE=220
PRINTS=6
# Editor-tunable settings: (default, minimum, maximum).
# drain and recharge are percent of charge per 10 seconds; lens_speed in field pixels per second.
SETTINGS={'needed':(3,1,6),'drain':(38,5,200),'recharge':(16,0,200),'lens_speed':(55,15,300)}
LAIR_DISTANCE=(3,6)


def settings_for(spec):
    spec=spec or {}
    return {key:spec.get(key,default) for key,(default,_,_) in SETTINGS.items()}


def validate_settings(spec,prefix=''):
    return [f'{prefix}Некоректне поле {key}: ціле число від {low} до {high}'
            for key,(_,low,high) in SETTINGS.items()
            if key in spec and (type(spec[key]) is not int or not low<=spec[key]<=high)]


def build_field(q,settings):
    """One group of prints in a random place; the direction of the steps points to the lair."""
    rng=random.Random(q['id']+':scanner')
    direction=rng.uniform(0,math.tau)
    cx,cy=rng.uniform(110,WIDTH-110),rng.uniform(100,HEIGHT-100)
    prints=[]
    for i in range(PRINTS):
        k=i-(PRINTS-1)/2;side=1 if i%2 else -1
        prints.append(dict(x=round(cx+math.cos(direction)*k*26-math.sin(direction)*9*side,1),
                           y=round(cy+math.sin(direction)*k*26+math.cos(direction)*9*side,1),found=False))
    q['scanner']=dict(prints=prints,center=[round(cx,1),round(cy,1)],direction=round(direction,4),
                      energy=100.0,lens=[WIDTH/2,HEIGHT/2],read=0,done=False,settings=settings,seed=rng.randrange(1<<30))


def world_angle(a,b):
    ax,ay=world_hex.center(a);bx,by=world_hex.center(b)
    return math.atan2(by-ay,bx-ax)


def angle_gap(a,b):
    d=abs(a-b)%math.tau
    return min(d,math.tau-d)


class TrackScannerMixin:
    def scanner_settings(self,q):
        import quest_profiles
        spec=quest_profiles.profile(q) or quest_profiles.defaults(KIND,bool(q.get('unique')))
        return settings_for(spec)

    def scanner_quest(self,ident=None):
        """Active elite hunt at its first point whose scanner search is not finished."""
        if self.battle or self.road_event:return None
        for q in self.quests:
            if (q['kind']==KIND and q['status']=='active' and q.get('track_index',0)==0 and q.get('pos')==[self.x,self.y]
                    and not q.get('scanner',{}).get('done') and (ident is None or q['id']==ident)):
                if 'scanner' not in q:build_field(q,self.scanner_settings(q))
                return q
        return None

    def search(self):
        q=self.scanner_quest()
        if q:
            if not q['scanner'].get('opened'):
                q['scanner']['opened']=True;self.turn+=1;self.rad_turns=max(0,self.rad_turns-1)
            self._scanner_request=q['id'];return True
        return super().search()

    def scanner_signal(self,q):
        s=q['scanner'];x,y=s['lens'];cx,cy=s['center']
        return max(0.0,1-math.hypot(x-cx,y-cy)/SIGNAL_RANGE)

    def scanner_tick(self,ident,dt,target,scanning):
        """Advance the scanner by dt seconds towards the hand position.

        Returns a dict with the number of newly read prints and whether the hunt was located.
        """
        q=self.scanner_quest(ident)
        result=dict(read=0,located=False,empty=False)
        if not q or type(dt) not in (int,float) or not math.isfinite(dt):return result
        if not (isinstance(target,(list,tuple)) and len(target)==2 and all(type(v) in (int,float) and math.isfinite(v) for v in target)):return result
        s=q['scanner'];cfg=s['settings'];dt=max(0.0,min(.1,dt))
        tx=max(0.0,min(WIDTH,target[0]));ty=max(0.0,min(HEIGHT,target[1]))
        if scanning and s['energy']<=0:scanning=False;result['empty']=True
        if not scanning:
            s['lens']=[tx,ty];s['energy']=min(100.0,s['energy']+dt*cfg['recharge']/10)
            return result
        x,y=s['lens'];d=math.hypot(tx-x,ty-y);step=min(d,cfg['lens_speed']*dt)
        if d>0:s['lens']=[x+(tx-x)/d*step,y+(ty-y)/d*step]
        s['energy']=max(0.0,s['energy']-dt*cfg['drain']/10)
        if s['energy']<=0:result['empty']=True
        x,y=s['lens']
        for p in s['prints']:
            if not p['found'] and math.hypot(p['x']-x,p['y']-y)<=READ_RADIUS:
                p['found']=True;s['read']+=1;result['read']+=1
        if s['read']>=cfg['needed']:result['located']=self.locate_lair(q)
        return result

    def lair_candidates(self,q):
        import monster_rules
        level=monster_rules.base_level(q['target_kind'])
        pos=tuple(q['pos'])
        return [list(p) for p in self.quest_locations(q)
                if tuple(p)!=pos and self.region_at(*p)>=level and LAIR_DISTANCE[0]<=world_hex.distance(pos,tuple(p))<=LAIR_DISTANCE[1]]

    def locate_lair(self,q):
        """Place the lair on the world map in the direction the prints lead."""
        s=q['scanner']
        if s['done']:return True
        pool=self.lair_candidates(q)
        if not pool:
            # Fall back to the point chosen when the quest was accepted.
            pool=[list(p) for p in q.get('track',[])[1:]] or [q['pos']]
        rng=random.Random(s['seed'])
        lair=min(pool,key=lambda p:(angle_gap(world_angle(q['pos'],p),s['direction']),abs(world_hex.distance(q['pos'],p)-4),rng.random()))
        s['done']=True;s['lair']=list(lair)
        q['track']=[q['pos'][:],list(lair)];q['track_index']=1;q['pos']=list(lair)
        self.reveal(*lair,0)
        self.log('Сліди прочитано. Лігво елітного мутанта позначено на мапі.')
        return True
