from i18n import t as tr
"""Delivery contracts and persistent radio-tuning puzzles."""
import afterdays as r
import frontier
import economy
import content
from reputation import Reputation
from border import Border

economy.BASE_REWARDS.update(delivery=90,radio=100)

class Game(Border, Reputation, frontier.Game):
    def __init__(self,seed=None):
        super().__init__(seed)
        content.migrate(self)
        self.init_reputation()

    @classmethod
    def load(cls,path):
        game=super().load(path)
        content.migrate(game)
        game.migrate_reputation_keys()
        return game

    def delivery_sites(self,q):
        origin=tuple(self.cities[q['city']]);reachable=self.player_reachable_world(origin)
        occupied={tuple(t['pos']) for t in self.quests if t['status']=='active' and t.get('pos')}
        return [s for s in self.special_sites if tuple(s['pos']) in reachable and tuple(s['pos'])!=origin
                and tuple(s['pos']) not in occupied and self.region_at(*s['pos'])<=q['level']+1]

    def _raw_mayor_offers(self):
        offers=frontier.Game.mayor_offers(self)
        if self.city not in self.mayors or self.battle:return offers
        for kind,title in [('delivery',tr('contracts.0001')),('radio',tr('contracts.0002'))]:
            if any(q['kind']==kind for q in offers):continue
            q=dict(id=r.uid(),kind=kind,city=self.city,status='offered',title=title,progress=0,goal=1,
                   target_kind=None,pos=None,unique=self.rng.random()<.18,scaled=True,distance_scaled=True,cycle_named=True,zone=self.region_level)
            self.price_quest(q)
            if kind=='delivery':
                pool=self.delivery_sites(q)
                if not pool:continue
                site=self.rng.choice(pool);q.update(destination=site['id'],destination_name=site['name'],pos=site['pos'][:])
            offers.append(q)
        content.migrate(self)
        return offers

    def accept_quest(self,quest_id):
        offer=next((q for q in self.mayor_offers() if q['id']==quest_id and q['status']=='offered'),None)
        if not offer or offer['kind'] not in ('delivery','radio'):return super().accept_quest(quest_id)
        if sum(q['status']=='active' for q in self.quests)>=8:
            self.log(tr('contracts.0003'));return False
        q=dict(offer)
        if q['kind']=='delivery':
            site=next((s for s in self.delivery_sites(q) if s['id']==q['destination']),None)
            if not site:self.log(tr('contracts.0004'));return False
            parcel=dict(id=r.uid(),type_id='quest_parcel',delivery=True,kind='quest',name=tr('contracts.0005')+q['destination_name'],rarity=0,weight=0,value=0,quest_id=q['id'])
            self.bag.append(parcel)
            # Reveal the recipient so its NPC and service are accessible on arrival.
            if not site['found']:self.discover(site['id'])
        else:
            pool=self.quest_locations(q)
            if not pool:self.log(tr('contracts.0006'));return False
            q['pos']=list(self.rng.choice(pool));q['radio_target']=[self.rng.randint(2,18) for _ in range(3)]
            q['radio_values']=[10,10,10];q['radio_attempts']=0
        q['status']='active';offer['status']='accepted';self.quests.append(q)
        self.log(tr('contracts.0007')+q['title']);self.emit(tr('contracts.0008'),color='#c7a0f1');return True

    def destination_quest(self):
        if self.battle or self.road_event:return None
        return next((q for q in self.quests if q['kind'] in ('delivery','radio') and q['status']=='active'
                     and not q['progress'] and q['pos']==[self.x,self.y]),None)

    def search(self):
        q=self.destination_quest()
        if not q:return super().search()
        if q['kind']=='delivery':
            parcel=next((i for i in self.bag if i.get('quest_id')==q['id']),None)
            if not parcel:self.log(tr('contracts.0009'));return False
            self.bag.remove(parcel);q['progress']=1
            self.log(tr('contracts.0010'));self.emit(tr('contracts.0011'),color='#99dca5')
        else:self._radio_request=q['id']
        return True

    def radio_signal(self,q,values):
        return max(0,100-round(sum(abs(a-b) for a,b in zip(q['radio_target'],values))*100/60))

    def tune_radio(self,quest_id,values):
        q=self.destination_quest()
        if not q or q['id']!=quest_id or q['kind']!='radio':return False
        if not isinstance(values,(tuple,list)) or len(values)!=3 or any(type(v)!=int or not 0<=v<=20 for v in values):return False
        q['radio_values']=list(values);q['radio_attempts']+=1;self.turn+=1;self.rad_turns=max(0,self.rad_turns-1)
        if all(abs(a-b)<=1 for a,b in zip(q['radio_target'],values)):
            q['progress']=1;self.log(tr('contracts.0012'));self.emit(tr('contracts.0013'),color='#99dca5');return True
        self.log(tr('contracts.0014'));return False

    def quest_text(self,q):
        if q['kind'] not in ('delivery','radio'):return super().quest_text(q)
        desc=(tr('contracts.0015')+q['destination_name']+tr('contracts.0016')) if q['kind']=='delivery' else tr('contracts.0017')
        state=tr('contracts.0018') if q['status']=='done' else tr('contracts.0019') if self.quest_ready(q) else tr('contracts.0020') if q['status']=='offered' else tr('contracts.0021')
        return tr('contracts.0023', v0='★ ' if q.get('unique') else '', v1=q['title'], v2=q['level'], v3=desc, v4=q.get('pos') or tr('contracts.0022'), v5=self.city_name(q['city']), v6=q['reward'], v7=q['xp_reward'], v8=state)+(tr('contracts.0024') if q.get('unique') else '')
