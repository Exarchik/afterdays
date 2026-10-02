"""Editor-authored offers use existing acceptance, objectives and turn-in logic."""
import copy
import quest_catalog as catalog
import afterdays as r
from metro035 import Game as BaseGame
from story_system import StoryMixin
from survival040 import Survival


class Game(Survival,StoryMixin,BaseGame):
    def price_quest(self,q):
        if q.get('authored_definition'):
            s=q['authored_definition'];q.update(reward=s['reward'],base_reward=s['reward'],xp_reward=s['xp_reward']);return
        return super().price_quest(q)

    def mayor_offers(self):
        native=super().mayor_offers()
        if self.city is None or self.battle or self.city not in self.mayors or self.road_event:return native
        specs=[s for s in self.authored_specs() if catalog.eligible(self,s)]
        if not specs:return native
        cache=self.reputation_state.setdefault('authored_offers',{})
        authored=[]
        for spec in specs:
            key=str(self.city)+':'+spec['id'];entry=cache.get(key)
            if entry and entry.get('status')!='offered':
                entry=None
            if entry and entry.get('authored_definition')!=spec:entry=None
            if entry is None:
                template=next((q for q in self.offers.get(str(self.city),[]) if q['kind']==spec['kind'] and 'metro_city' not in q),None)
                if template is None and spec['kind'] in ('hunt','retrieve','scout','supplies','purge'):
                    template=dict(kind=spec['kind'],city=self.city,level=self.region_level,zone=self.region_level,
                                  progress=0,goal=1,target_kind=None,pos=None,scaled=True,distance_scaled=True,cycle_named=True)
                if template is None:continue
                entry=copy.deepcopy(template);ident=r.uid()
                for field in ('test_item','repair_item'):
                    if field in entry:entry[field]['quest_id']=ident;entry[field]['id']=r.uid()
                entry.update(id=ident,authored_id=spec['id'],authored_definition=copy.deepcopy(spec),title=spec['title'],
                             status='offered',progress=0,unique=False,reward_items=[],reward_unique=False)
                if spec['kind'] in ('hunt','trophies'):entry['goal']=spec['goal']
                if spec['kind']=='supplies':entry.update(food_need=spec['food_need'],med_need=spec['med_need'])
                self.price_quest(entry);cache[key]=entry
            authored.append(entry)
        slots=max(0,self.quest_capacity(self.city)-len(self.active_for(self.city)))
        return (authored+native)[:slots]

    def accept_quest(self,ident):
        offer=next((q for q in self.mayor_offers() if q['id']==ident),None)
        if offer and offer.get('authored_id') and not catalog.eligible(self,offer['authored_definition']):return False
        return super().accept_quest(ident)

    def turn_in(self,ident):
        q=next((q for q in self.quests if q['id']==ident),None)
        ok=super().turn_in(ident)
        if ok and q and q.get('authored_id'):self.reputation_state.setdefault('authored_history',{})[q['authored_id']]=self.turn
        if ok:self.story_sync()
        return ok

    def abandon_quest(self,ident):
        q=next((q for q in self.quests if q['id']==ident),None)
        ok=super().abandon_quest(ident)
        if ok and q and q.get('authored_id'):
            self.reputation_state.setdefault('authored_history',{})[q['authored_id']]=self.turn
            for entry in self.reputation_state.get('authored_offers',{}).values():
                if entry['id']==ident:entry['status']='cancelled'
        return ok

    def quest_text(self,q):
        text=super().quest_text(q)
        spec=q.get('authored_definition')
        return spec['description']+'\n\n'+text if spec and spec['description'] else text
