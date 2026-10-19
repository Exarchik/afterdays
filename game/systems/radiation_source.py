"""Dosimeter contracts: locate a lost radiation source, carry the device back to the quest giver."""
import random

import world_hex
from game.catalog import uid

KIND='radiation_source'
TITLE='Пошук джерела випромінювання'
# Editor-tunable minigame settings and their limits: (default, minimum, maximum).
SETTINGS={'grid_size':(6,4,8),'max_dose':(5,0,20),'device_radiation':(1,0,10)}
PEAK=42.18
RADIATION_ART='effects:radiation_damage'
DEVICE_TYPE='quest_radioactive_device'
DEVICE_NAME='Радіоактивний прилад'
DEVICE_WEIGHT=1.0


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


def reading_at(q,cell):
    """Deterministic µSv/h value; falls off with hex distance to the source."""
    d=world_hex.distance(tuple(cell),tuple(q['rad_source']))
    noise=random.Random(f"radiation-reading:{q['id']}:{q['rad_attempt']}:{cell[0]},{cell[1]}").uniform(.92,1.08)
    return round((.18+42/(1+1.9*d*d))*noise,2)


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
        size=settings['grid_size']
        rng=random.Random(f"radiation-source:{q['id']}:{attempt}")
        q.update(rad_attempt=attempt,rad_source=[rng.randrange(size),rng.randrange(size)],rad_probes=[])
        q.setdefault('rad_dose',0)

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
        return next((q for q in self.quests if q['id']==ident and q['kind']==KIND and q['status']=='active'),None)

    def radiation_available(self,q):
        return bool(q and q['status']=='active' and q['progress']<q['goal'] and not self.battle and not self.road_event
                    and q.get('pos')==[self.x,self.y])

    def _radiation_cell(self,q,x,y):
        size=q['rad_settings']['grid_size']
        return type(x) is int and type(y) is int and 0<=x<size and 0<=y<size

    def probe_radiation(self,ident,x,y):
        """Measure one cell; measuring the source itself finds the device. None if not allowed.

        Probes are unlimited: the only cost of a long search is the radiation picked up.
        """
        q=self.radiation_quest(ident)
        if not self.radiation_available(q) or not self._radiation_cell(q,x,y):return None
        if any(p['cell']==[x,y] for p in q['rad_probes']):return None
        value=reading_at(q,(x,y));q['rad_probes'].append(dict(cell=[x,y],value=value))
        dose=min(q['rad_settings']['max_dose'],round(q['rad_settings']['max_dose']*value/PEAK))
        if dose>0:
            q['rad_dose']+=dose
            if not self.add_radiation(dose):return value
        if [x,y]==q['rad_source']:self._pick_up_device(q)
        return value

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
        elif q['status']=='offered':state=f"Дозиметр: ділянка {settings['grid_size']}×{settings['grid_size']} гексів, заміри без обмежень; кожен додає радіацію."
        else:state=f"Зроблено замірів: {len(q.get('rad_probes',[]))}. Отримано радіації: {q.get('rad_dose',0)}."
        point=f"\nДілянка пошуку: [{q['pos'][0]}; {q['pos'][1]}]." if q.get('pos') else ''
        return (f"{q['title']}\n{state}{point}\nЗамовник: {self.city_name(q['city'])}. Знайдений прилад треба принести замовнику.\n"
                f"Нагорода: {q.get('reward',0)} кр. · {q.get('xp_reward',0)} XP")
