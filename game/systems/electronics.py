"""Persistent circuit-board installation contracts."""
import random
from game.catalog import uid
KIND='electronics_repair'
TITLE='Ремонт електронного обладнання'

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

    def init_circuit_board(self,q):
        if q.get('circuit_version')==2:return
        rng=random.Random('circuit-board:'+q['id'])
        pieces=q.get('circuit_target') or rng.sample(range(16),6)
        q['circuit_target']=pieces
        q['circuit_angles']=[rng.randrange(4) for _ in pieces]
        inventory=pieces[:];rng.shuffle(inventory)
        q['circuit_inventory']=inventory
        completed=q.get('circuit_checked',False)
        q['circuit_slots']=pieces[:] if completed else [None]*6
        q['circuit_rotations']={str(p):(q['circuit_angles'][i] if completed else rng.randrange(4)) for i,p in enumerate(pieces)}
        q['circuit_version']=2
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
        if not q or type(piece) is not int or piece not in q['circuit_target']:return False
        if slot is not None and (type(slot) is not int or not 0<=slot<6):return False
        slots=q['circuit_slots']
        if piece in slots:slots[slots.index(piece)]=None
        # An occupied socket's former module goes back to the tray.
        if slot is not None:slots[slot]=piece
        return True

    def rotate_circuit(self,ident,piece):
        q=self.circuit_editable(ident)
        if not q or type(piece) is not int or piece not in q['circuit_target']:return False
        rotations=q['circuit_rotations'];rotations[str(piece)]=(rotations[str(piece)]+1)%4;return True

    def circuit_matches(self,q):
        return q.get('circuit_slots')==q.get('circuit_target') and all(q.get('circuit_rotations',{}).get(str(p))==angle for p,angle in zip(q.get('circuit_target',[]),q.get('circuit_angles',[])))

    def check_circuits(self,ident):
        q=self.circuit_editable(ident)
        if not q or not self.circuit_matches(q):return False
        q['circuit_checked']=True;q['progress']=1
        self.log('Контакти з’єднані. Електроніку відновлено — поверніться до замовника.');return True

    def quest_ready(self,q):
        if q['kind']==KIND:return q['status']=='active' and q.get('circuit_checked',False) and self.circuit_matches(q)
        return super().quest_ready(q)

    def quest_text(self,q):
        if q['kind']!=KIND:return super().quest_text(q)
        state='Електроніку відновлено — поверніться до замовника.' if q.get('circuit_checked') else 'На місці поломки встановіть мікросхеми: форма та клеми мають збігатися. ПКМ — поворот на 90°. Після монтажу увімкніть живлення.'
        point=f"\nМісце ремонту: [{q['pos'][0]}; {q['pos'][1]}]." if q.get('pos') else ''
        return (f"{q['title']}\n{state}{point}\nЗамовник: {self.city_name(q['city'])}.\n"
                f"Нагорода: {q.get('reward',0)} кр. · {q.get('xp_reward',0)} XP")
