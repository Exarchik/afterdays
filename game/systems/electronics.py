"""Persistent circuit-board installation contracts.

Sockets show only their contact pads; a module fits when every contact lands on a pad and
contact 1 lands on the square pad. Contact layouts are generated per quest on the visible
edge of the module art (circuit_art), so they cannot be memorised.
"""
import math
import random
from game.catalog import uid
import circuit_art
KIND='electronics_repair'
TITLE='Ремонт електронного обладнання'
SLOTS=6
VERSION=3
TOLERANCE=7   # pixels in 150-px tile coordinates
# Editor-tunable settings: (default, minimum, maximum).
SETTINGS={'contacts_min':(3,2,5),'contacts_max':(5,3,6),'decoys':(1,0,3),'hints':(1,0,1),'shock':(0,0,5)}


def settings_for(spec):
    spec=spec or {}
    return {key:spec.get(key,default) for key,(default,_,_) in SETTINGS.items()}


def validate_settings(spec,prefix=''):
    errors=[f'{prefix}Некоректне поле {key}: ціле число від {low} до {high}'
            for key,(_,low,high) in SETTINGS.items()
            if key in spec and (type(spec[key]) is not int or not low<=spec[key]<=high)]
    values=settings_for(spec)
    if not errors and values['contacts_min']>values['contacts_max']:
        errors.append(f'{prefix}Мінімум контактів не може бути більшим за максимум')
    return errors


def contacts_at(q,piece,angle):
    """Contacts of a module rotated by angle, in tile coordinates; contact 1 first."""
    return [circuit_art.rotate(c,angle) for c in q['circuit_contacts'][str(piece)]]


def pads(q,slot):
    return contacts_at(q,q['circuit_target'][slot],q['circuit_angles'][slot])


def fit(q,piece,angle,slot):
    """How a module would sit in a socket: which pads and contacts meet, and whether it fits."""
    board=pads(q,slot);module=contacts_at(q,piece,angle)
    near=lambda a,b:math.dist(a,b)<=TOLERANCE
    pad_hits=[any(near(c,p) for c in module) for p in board]
    contact_hits=[any(near(c,p) for p in board) for c in module]
    pin1=near(module[0],board[0])
    return dict(pads=pad_hits,contacts=contact_hits,pin1=pin1,ok=all(pad_hits) and all(contact_hits) and pin1)

class ElectronicsRepairMixin:
    def _raw_mayor_offers(self):
        offers=super()._raw_mayor_offers()
        if self.city in self.mayors and not any(q['kind']==KIND for q in offers):
            level=self.region_at(*self.cities[self.city])
            q=dict(id=uid(),kind=KIND,city=self.city,title=TITLE,status='offered',progress=0,goal=1,
                   pos=None,target_kind=None,unique=False,level=level,zone=level,scaled=True,distance_scaled=True,cycle_named=True)
            self.price_quest(q);offers.append(q)
        return offers

    def circuit_locations(self,q):
        sites={tuple(s['pos']) for s in self.special_sites}
        return [list(p) for p in self.quest_locations(q) if tuple(p) not in sites and list(p) not in self.cities and list(p)!=[self.x,self.y]]

    def circuit_settings(self,q):
        import quest_profiles
        spec=quest_profiles.profile(q) or quest_profiles.defaults(KIND,bool(q.get('unique')))
        return settings_for(spec)

    def init_circuit_board(self,q):
        if q.get('circuit_version')==VERSION:return
        rng=random.Random('circuit-board:'+q['id'])
        settings=q.get('circuit_settings') or self.circuit_settings(q)
        pieces=q.get('circuit_target') or rng.sample(range(circuit_art.PIECES),SLOTS)
        q['circuit_target']=pieces
        if len(q.get('circuit_angles') or [])!=len(pieces):q['circuit_angles']=[rng.randrange(4) for _ in pieces]
        completed=q.get('circuit_checked',False)
        spare=[p for p in range(circuit_art.PIECES) if p not in pieces]
        decoys=[] if completed else random.Random('circuit-decoys:'+q['id']).sample(spare,settings['decoys'])
        inventory=pieces+decoys;rng.shuffle(inventory)
        q['circuit_inventory']=inventory
        def contacts(piece):
            # Per piece, so the layout does not depend on the tray order.
            r=random.Random(f"circuit-contacts:{q['id']}:{piece}")
            return circuit_art.choose_contacts(r,piece,r.randint(settings['contacts_min'],settings['contacts_max']))
        q['circuit_contacts']={str(p):contacts(p) for p in inventory}
        old=q.get('circuit_rotations',{})
        q['circuit_slots']=pieces[:] if completed else [s if s in pieces else None for s in (q.get('circuit_slots') or [None]*SLOTS)]
        q['circuit_rotations']={str(p):(q['circuit_angles'][pieces.index(p)] if completed else old.get(str(p),rng.randrange(4))) for p in inventory}
        q['circuit_settings']=settings;q['circuit_bad']=[]
        q['circuit_version']=VERSION
        q.pop('circuit_layout',None)

    def migrate_circuit_quests(self):
        for q in self.quests:
            if q['kind']!=KIND:continue
            self.init_circuit_board(q)
            if q['status']=='active' and not q.get('circuit_checked') and not q.get('pos'):
                pool=self.circuit_locations(q)
                if pool:q['pos']=random.Random('circuit-location:'+q['id']).choice(pool);self.reveal(*q['pos'],0)

    def accept_quest(self,ident):
        offer=next((q for q in self.mayor_offers() if q['id']==ident),None)
        pool=None
        if offer and offer['kind']==KIND:
            pool=self.circuit_locations(offer)
            if not pool:self.log('Немає доступного місця для ремонту електроніки.');return False
        ok=super().accept_quest(ident)
        if ok and pool:
            q=self.electronics_quest(ident);self.init_circuit_board(q)
            q.update(pos=random.Random('circuit-location:'+ident).choice(pool),circuit_checked=False,goal=1,progress=0)
            self.reveal(*q['pos'],0)
        return ok

    def electronics_quest(self,ident):
        return next((q for q in self.quests if q['id']==ident and q['kind']==KIND and q['status']=='active'),None)

    def electronics_available(self,q):
        return bool(q and q['status']=='active' and not self.battle and not self.road_event and q.get('pos')==[self.x,self.y])

    def circuit_editable(self,ident):
        q=self.electronics_quest(ident)
        return q if self.electronics_available(q) and not q.get('circuit_checked') else None

    def place_circuit(self,ident,piece,slot):
        q=self.circuit_editable(ident)
        if not q or type(piece) is not int or piece not in q['circuit_inventory']:return False
        if slot is not None and (type(slot) is not int or not 0<=slot<SLOTS):return False
        slots=q['circuit_slots']
        if piece in slots:slots[slots.index(piece)]=None
        # An occupied socket's former module goes back to the tray.
        if slot is not None:slots[slot]=piece
        q['circuit_bad']=[]
        return True

    def rotate_circuit(self,ident,piece):
        q=self.circuit_editable(ident)
        if not q or type(piece) is not int or piece not in q['circuit_inventory']:return False
        rotations=q['circuit_rotations'];rotations[str(piece)]=(rotations[str(piece)]+1)%4
        q['circuit_bad']=[];return True

    def circuit_fit(self,q,piece,slot):
        """Live hint while dragging: pads and contacts that meet in this socket."""
        return fit(q,piece,q['circuit_rotations'][str(piece)],slot)

    def circuit_faults(self,q):
        return [i for i,p in enumerate(q.get('circuit_slots',[])) if p is None or not fit(q,p,q['circuit_rotations'][str(p)],i)['ok']]

    def circuit_matches(self,q):
        return q.get('circuit_version')==VERSION and len(q.get('circuit_slots',[]))==SLOTS and not self.circuit_faults(q)

    def check_circuits(self,ident):
        """Power on: sparks on badly fitted sockets (optional shock), success when every module fits."""
        q=self.circuit_editable(ident)
        if not q or None in q['circuit_slots']:return False
        bad=self.circuit_faults(q);q['circuit_bad']=bad
        if bad:
            shock=q.get('circuit_settings',{}).get('shock',0)
            names=', '.join(f'U{i+1}' for i in bad)
            if shock:
                self.hp=max(1,self.hp-shock)
                self.log(f'Іскра на {names}! Вас ударило струмом: −{shock} HP.')
            else:self.log(f'Іскра на {names}: контакти не лягли на клеми.')
            return False
        q['circuit_checked']=True;q['progress']=1
        self.log('Контакти з’єднані. Електроніку відновлено — поверніться до замовника.');return True

    def quest_ready(self,q):
        if q['kind']==KIND:return q['status']=='active' and q.get('circuit_checked',False) and self.circuit_matches(q)
        return super().quest_ready(q)

    def quest_text(self,q):
        if q['kind']!=KIND:return super().quest_text(q)
        state='Електроніку відновлено — поверніться до замовника.' if q.get('circuit_checked') else 'На місці поломки встановіть мікросхеми: контакти модуля мають лягти на клеми гнізда, контакт 1 — на квадратну клему. ПКМ або R — поворот на 90°. Після монтажу увімкніть живлення.'
        point=f"\nМісце ремонту: [{q['pos'][0]}; {q['pos'][1]}]." if q.get('pos') else ''
        return (f"{q['title']}\n{state}{point}\nЗамовник: {self.city_name(q['city'])}.\n"
                f"Нагорода: {q.get('reward',0)} кр. · {q.get('xp_reward',0)} XP")
