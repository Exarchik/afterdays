"""Dosimeter contracts: locate a lost radiation source, carry the device back to the quest giver."""
import math
import random

from game.catalog import uid

KIND='radiation_source'
TITLE='Пошук джерела випромінювання'
# Editor-tunable minigame settings and their limits: (default, minimum, maximum).
SETTINGS={'grid_size':(6,4,8),'isotopes':(3,0,4),'max_dose':(5,0,20),'device_radiation':(1,0,10)}
PEAK=42.18
BACKGROUND=.18
RADIATION_ART='effects:radiation_damage'
DEVICE_TYPE='quest_radioactive_device'
DEVICE_NAME='Радіоактивний прилад'
DEVICE_WEIGHT=1.0
# Stray sources that "light up" the plot, strongest first; the first one masks the device.
ISOTOPES=(('cs137','уламок із цезієм-137',42),('co60','джерело кобальт-60',30),
          ('sr90','шматок РІТЕГа зі стронцієм-90',20),('ra226','стара шкала з радієм-226',12))
DEVICE_POWER=7
DIG_RADIUS=.45      # how close (in field units) a dig must be to lift a source
SWEEP_RATE=.25      # radiation per second over the source = max_dose*SWEEP_RATE
MAX_SWEEP=.5        # longest time step accepted from the UI, seconds
MAX_HOLES=60


def settings_for(spec):
    """Minigame settings from a quest profile, falling back to defaults."""
    spec=spec or {}
    return {key:spec.get(key,default) for key,(default,_,_) in SETTINGS.items()}


def device_art(spec):
    """Art ID for the carried device; empty means the generic quest-item icon."""
    return (spec or {}).get('device_art','')


def validate_settings(spec,prefix=''):
    errors=[]
    for key,(_,low,high) in SETTINGS.items():
        if key in spec and (type(spec[key]) is not int or not low<=spec[key]<=high):
            errors.append(f'{prefix}Некоректне поле {key}: ціле число від {low} до {high}')
    if 'device_art' in spec and not isinstance(spec['device_art'],str):errors.append(prefix+'Некоректне поле device_art')
    return errors


def is_device(item,q=None):
    return item.get('type_id')==DEVICE_TYPE and (q is None or item.get('quest_id')==q['id'])


def area(settings):
    """Plot size in field units (one unit ≈ the falloff step of a source)."""
    size=settings['grid_size']
    return size*2.5,size*1.55


def power(source):
    return DEVICE_POWER if source['kind']=='device' else next(p for k,_,p in ISOTOPES if k==source['kind'])


def source_name(source):
    return DEVICE_NAME.lower() if source['kind']=='device' else next(n for k,n,_ in ISOTOPES if k==source['kind'])


def place_sources(ident,attempt,settings):
    """Device plus stray isotopes; the strongest stray lies 2.2–3 units from the device and masks it."""
    rng=random.Random(f"radiation-source:{ident}:{attempt}")
    w,h=area(settings)
    def point(margin):return [round(rng.uniform(margin,w-margin),2),round(rng.uniform(margin,h-margin),2)]
    def inside(p):return 1<=p[0]<=w-1 and 1<=p[1]<=h-1
    device=point(1.6);sources=[dict(kind='device',x=device[0],y=device[1],found=False)]
    for n,(kind,_,_) in enumerate(ISOTOPES[:settings.get('isotopes',0)]):
        for _ in range(200):
            if n==0:
                a=rng.uniform(0,2*math.pi);d=rng.uniform(2.2,3.0)
                p=[round(device[0]+math.cos(a)*d,2),round(device[1]+math.sin(a)*d,2)]
                if inside(p):break
            else:
                p=point(1)
                if all(math.dist(p,(s['x'],s['y']))>=3.2 for s in sources):break
        else:p=point(1)
        sources.append(dict(kind=kind,x=p[0],y=p[1],found=False))
    return sources


def reading(q,x,y):
    """µSv/h at a field point: background plus every source still in the ground."""
    value=BACKGROUND
    for s in q.get('rad_sources',[]):
        if not s['found']:value+=power(s)/(1+1.9*((x-s['x'])**2+(y-s['y'])**2))
    return value


class RadiationSourceMixin:
    def _raw_mayor_offers(self):
        offers=super()._raw_mayor_offers()
        if self.city in self.mayors and not any(q['kind']==KIND for q in offers):
            level=self.region_at(*self.cities[self.city])
            q=dict(id=uid(),kind=KIND,city=self.city,title=TITLE,status='offered',progress=0,goal=1,
                   pos=None,target_kind=None,unique=False,level=level,zone=level,scaled=True,distance_scaled=True,cycle_named=True)
            q['quest_art']=RADIATION_ART
            self.price_quest(q);offers.append(q)
        return offers

    def radiation_locations(self,q):
        sites={tuple(s['pos']) for s in self.special_sites}
        return [list(p) for p in self.quest_locations(q) if tuple(p) not in sites and list(p) not in self.cities and list(p)!=[self.x,self.y]]

    def _radiation_profile(self,q):
        import quest_profiles
        return quest_profiles.profile(q) or quest_profiles.defaults(KIND,bool(q.get('unique')))

    def _radiation_settings(self,q):
        return settings_for(self._radiation_profile(q))

    def init_radiation_board(self,q,attempt=0):
        settings=q.setdefault('rad_settings',self._radiation_settings(q))
        for key,(default,_,_) in SETTINGS.items():settings.setdefault(key,default)
        q.update(rad_attempt=attempt,rad_sources=place_sources(q['id'],attempt,settings),rad_holes=[],rad_dose_left=0.0)
        q.setdefault('rad_dose',0)
        for key in ('rad_source','rad_probes'):q.pop(key,None)

    def accept_quest(self,ident):
        offer=next((q for q in self.mayor_offers() if q['id']==ident),None)
        pool=None
        if offer and offer['kind']==KIND:
            pool=self.radiation_locations(offer)
            if not pool:self.log('Немає доступної ділянки для пошуку джерела.');return False
        ok=super().accept_quest(ident)
        if ok and pool:
            q=self.radiation_quest(ident)
            q.update(pos=random.Random('radiation-location:'+ident).choice(pool),goal=1,progress=0)
            self.init_radiation_board(q);self.reveal(*q['pos'],0)
        return ok

    def radiation_quest(self,ident):
        q=next((q for q in self.quests if q['id']==ident and q['kind']==KIND and q['status']=='active'),None)
        # Saves from the hex-probe version: re-plant the plot, keep the dose already taken.
        if q and 'rad_sources' not in q and q['progress']<q['goal']:self.init_radiation_board(q,q.get('rad_attempt',0))
        return q

    def radiation_available(self,q):
        return bool(q and q['status']=='active' and q['progress']<q['goal'] and not self.battle and not self.road_event
                    and q.get('pos')==[self.x,self.y])

    def _radiation_point(self,q,x,y):
        w,h=area(q['rad_settings'])
        return all(type(v) in (int,float) and not isinstance(v,bool) for v in (x,y)) and 0<=x<=w and 0<=y<=h

    def _irradiate(self,q,amount):
        """Fractional dose accumulates; whole points go to the player."""
        q['rad_dose_left']=q.get('rad_dose_left',0.0)+amount
        whole=int(q['rad_dose_left']);q['rad_dose_left']-=whole
        if whole<=0:return True
        q['rad_dose']=q.get('rad_dose',0)+whole
        return self.add_radiation(whole)

    def radiation_sweep(self,ident,x,y,seconds):
        """The probe over point (x,y) for some seconds: returns the reading and costs radiation.

        No limits: the only cost of a long search is the dose picked up while sweeping.
        """
        q=self.radiation_quest(ident)
        if not self.radiation_available(q) or not self._radiation_point(q,x,y):return None
        value=reading(q,x,y)
        seconds=max(0.0,min(MAX_SWEEP,float(seconds)))
        self._irradiate(q,q['rad_settings']['max_dose']*SWEEP_RATE*value/PEAK*seconds)
        return value

    def dig_radiation(self,ident,x,y):
        """Dig at (x,y). Lifts the nearest source within reach into the lead container.

        Returns dict(result='empty'|'isotope'|'device', name, dose) or None if not allowed.
        A miss leaves a hole and costs radiation as if standing there.
        """
        q=self.radiation_quest(ident)
        if not self.radiation_available(q) or not self._radiation_point(q,x,y):return None
        left=[s for s in q['rad_sources'] if not s['found']]
        near=min(left,key=lambda s:math.dist((x,y),(s['x'],s['y'])),default=None)
        if near and math.dist((x,y),(near['x'],near['y']))<=DIG_RADIUS:
            near['found']=True;near['order']=sum(s['found'] for s in q['rad_sources'])
            if near['kind']=='device':
                self._pick_up_device(q);return dict(result='device',name=DEVICE_NAME,dose=0)
            self.log(f'Вилучено: {source_name(near)}. Не те, що шукали, — у свинцевий контейнер.')
            return dict(result='isotope',name=source_name(near),dose=0)
        settings=q['rad_settings']
        dose=min(settings['max_dose'],round(settings['max_dose']*reading(q,x,y)/PEAK))
        q['rad_holes']=(q.get('rad_holes',[])+[[round(x,2),round(y,2)]])[-MAX_HOLES:]
        if dose>0:
            q['rad_dose']=q.get('rad_dose',0)+dose;self.add_radiation(dose)
        return dict(result='empty',name='',dose=dose)

    def radiation_cleared(self,q):
        """Stray sources lifted so far."""
        return sum(s['found'] and s['kind']!='device' for s in q.get('rad_sources',[]))

    def _pick_up_device(self,q):
        q['progress']=q['goal']
        # The source itself becomes a quest item that keeps irradiating its carrier.
        art=device_art(self._radiation_profile(q))
        item=dict(id=uid(),type_id=DEVICE_TYPE,kind='quest',name=DEVICE_NAME,rarity=0,weight=DEVICE_WEIGHT,value=0,quest_id=q['id'])
        if art:item['sprite_id']=art
        self.bag.append(item)
        self.log(f'Джерело випромінювання знайдено. Ви підняли радіоактивний прилад — віднесіть його замовнику ({self.city_name(q["city"])}).')

    def carried_devices(self):
        return [i for i in self.bag if is_device(i)]

    def _world_time_tick(self):
        """Each world step with the device in the backpack adds radiation; radioprotectors block it."""
        protected=self.rad_turns>0
        ok=super()._world_time_tick()
        if not ok or protected or self.battle:return ok
        carrying=[q for q in self.quests if q['kind']==KIND and q['status']=='active' and any(is_device(i,q) for i in self.bag)]
        dose=0
        for q in carrying:
            rate=q.get('rad_settings',{}).get('device_radiation',1)
            q['rad_dose']=q.get('rad_dose',0)+rate;dose+=rate
        return self.add_radiation(dose) if dose>0 else ok

    def turn_in(self,ident):
        q=next((q for q in self.quests if q['id']==ident),None)
        ok=super().turn_in(ident)
        if ok and q and q['kind']==KIND:
            # The quest giver takes the device away.
            for items in (self.bag,self.stash,self.loot):items[:]=[i for i in items if not is_device(i,q)]
        return ok

    def quest_item_views(self,q):
        if q['kind']!=KIND:return super().quest_item_views(q)
        device=next((i for i in self.bag if is_device(i,q)),None)
        if device:return [device]
        preview=dict(id='preview',type_id=DEVICE_TYPE,kind='quest',name=DEVICE_NAME,rarity=0,weight=DEVICE_WEIGHT,value=0)
        art=device_art(self._radiation_profile(q))
        if art:preview['sprite_id']=art
        return [preview]

    def quest_ready(self,q):
        if q['kind']==KIND:return q['status']=='active' and q['progress']>=q['goal'] and any(is_device(i,q) for i in self.bag)
        return super().quest_ready(q)

    def quest_text(self,q):
        if q['kind']!=KIND:return super().quest_text(q)
        settings=q.get('rad_settings') or self._radiation_settings(q)
        rate=settings.get('device_radiation',1)
        if q['status']=='done':state='Прилад передано замовнику. Квест виконано.'
        elif q['progress']>=q['goal'] and any(is_device(i,q) for i in self.bag):
            state=f"Радіоактивний прилад у рюкзаку: +{rate} радіації за кожен крок (радіопротектор захищає). Віднесіть його замовнику."
        elif q['progress']>=q['goal']:state='Джерело знайдено, але прилада немає в рюкзаку. Поверніть його, щоб здати квест.'
        elif q['status']=='offered':
            stray=settings.get('isotopes',0)
            state=("Дозиметр: ведіть щуп по ділянці, поки він у полі, набігає радіація."
                   +(f" Окрім приладу, там ще {stray} сторонніх джерел, що його засвічують." if stray else ''))
        else:state=f"Вилучено сторонніх джерел: {self.radiation_cleared(q)}. Розкопів: {len(q.get('rad_holes',[]))+sum(s['found'] for s in q.get('rad_sources',[]))}. Отримано радіації: {q.get('rad_dose',0)}."
        point=f"\nДілянка пошуку: [{q['pos'][0]}; {q['pos'][1]}]." if q.get('pos') else ''
        return (f"{q['title']}\n{state}{point}\nЗамовник: {self.city_name(q['city'])}. Знайдений прилад треба принести замовнику.\n"
                f"Нагорода: {q.get('reward',0)} кр. · {q.get('xp_reward',0)} XP")
