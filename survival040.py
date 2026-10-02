"""Version 0.40: persistent radiation injury, satiety and travel regeneration."""
import math
from i18n import t as tr


class Survival:
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self._init_survival()

    def _init_survival(self):
        state=self.reputation_state.setdefault('survival040',{})
        for key,value in dict(radiation=0,hunger=20,regen_remainder=0).items():state.setdefault(key,value)
        # Old timed immunity is superseded by treatment of accumulated injury.
        self.rad_turns=0

    @property
    def survival(self):return getattr(self,'reputation_state',{}).get('survival040',{})

    @property
    def radiation_injury(self):return self.survival.get('radiation',0)

    @property
    def hunger(self):return self.survival.get('hunger',20)

    @property
    def radiation_sickness(self):return self.radiation_injury>=50

    @property
    def starving(self):return self.hunger<0

    @property
    def healthy_max_hp(self):return super().max_hp

    @property
    def max_hp(self):return max(0,math.ceil(self.healthy_max_hp*(100-self.radiation_injury)/100))

    @property
    def max_ap(self):return max(1,super().max_ap-(2 if self.starving else 0))

    @property
    def outgoing_damage_multiplier(self):return .7 if self.radiation_sickness else 1

    def incoming_combat_damage(self,amount):
        return max(1,round(amount*1.3)) if self.radiation_sickness else amount

    def _sync_ap(self):
        if self.battle:
            self.battle['max_ap']=self.max_ap
            self.battle['ap']=min(self.battle['ap'],self.max_ap)

    def add_radiation(self,amount=5):
        self.survival['radiation']=min(100,self.radiation_injury+amount)
        self.hp=min(self.hp,self.max_hp)
        self.emit(tr('survival040.radiation_gain',amount=amount),color='#e56860')
        if self.hp<=0:
            self.log(tr('survival040.radiation_death'));self.defeat();return False
        return True

    def regenerate(self,amount):
        healed=max(0,min(self.max_hp-self.hp,amount))
        if healed:self.hp+=healed;self.emit(f'+{healed:g} HP',color='#9cdda8')
        return healed

    def _after_combat(self,battle):
        if battle and not battle.get('survival040_regenerated'):
            battle['survival040_regenerated']=True
            self.regenerate(max(0,self.protection_stat('regen')))

    def victory(self):
        battle=self.battle
        result=super().victory()
        if battle and (self.battle is None or self.battle.get('cleared')):self._after_combat(battle)
        return result

    def flee(self):
        battle=self.battle;ok=super().flee()
        if ok and self.battle is None:self._after_combat(battle)
        return ok

    @staticmethod
    def food_satiety(item):
        # Content definition permits future food types without changing the eating rules.
        import content
        definition=content.CONSUMABLES.get(item.get('type_id'),{})
        return max(1,int(item.get('satiety',definition.get('satiety',10))))

    def simplest_food(self):
        foods=[i for i in self.bag if i['kind']=='food' and i.get('qty',1)>0 and not i.get('quest_id')]
        return min(foods,key=lambda i:(i.get('rarity',0),self.food_satiety(i),i.get('value',0)),default=None)

    def eat(self,automatic=False):
        import progression as p
        item=self.simplest_food()
        if not item or self.hunger>=20 or (not automatic and self.battle and self.battle['ap']<2):return False
        amount=self.food_satiety(item);name=item['name']
        p.extract(self.bag,item,1)
        self.survival['hunger']=min(20,self.hunger+amount)
        if not automatic and self.battle:self.battle['ap']-=2
        self._sync_ap()
        self.emit(tr('survival040.ate',name=name,amount=amount),color='#65b3ed')
        return True

    def can_use_consumable(self,kind):
        if self.battle and self.battle['ap']<2:return False
        if kind=='food':return self.hunger<20 and self.simplest_food() is not None
        if kind=='rad':return self.radiation_injury>0 and self.count('rad')>0
        return kind=='med' and self.hp<self.max_hp and self.count('med')>0

    def use(self,kind):
        if kind=='food':return self.eat()
        if kind=='rad':
            if not self.can_use_consumable(kind):return False
            removed=min(50,self.radiation_injury)
            self.consume('rad');self.survival['radiation']-=removed
            if self.battle:self.battle['ap']-=2
            self._sync_ap()
            self.emit(tr('survival040.radiation_cured',amount=removed),color='#9cdda8')
            return True
        return super().use(kind)

    def rest(self):
        if self.radiation_injury or self.starving:
            message=tr('survival040.no_sleep_rad' if self.radiation_injury else 'survival040.no_sleep_hunger')
            self.log(message);self.emit(message,color='#e56860');return False
        return super().rest()

    def step(self,dx,dy):
        # One survival update per entered cell, including diagonal movement.
        previous=getattr(self,'_survival_step',None)
        self._survival_step=False
        try:return super().step(dx,dy)
        finally:self._survival_step=previous

    def _world_time_tick(self):
        self.turn+=1;self.travel_steps+=1
        self.advance_storm()
        if getattr(self,'_survival_step',None) is True:return True
        if getattr(self,'_survival_step',None) is False:self._survival_step=True
        self.survival['hunger']-=1
        while self.hunger<1 and self.eat(automatic=True):pass
        if self.hunger<=-20:
            self.log(tr('survival040.starved'));self.defeat();return False
        irradiated=f'{self.x},{self.y}' in self.radiation
        storm=not self.regular_city and not getattr(self,'_guided_trip',False) and (self.x,self.y) in self.storm_cells()
        if (irradiated or storm) and not self.add_radiation():return False
        total=self.survival['regen_remainder']+max(0,self.protection_stat('regen'))
        healing=int(total//30);self.survival['regen_remainder']=total-healing*30
        self.regenerate(healing)
        self._sync_ap()
        return True

    def hurt_world(self,damage,label=None):
        # Searching under a storm uses the same radiation injury instead of ordinary HP damage.
        if label==tr('update033.storm_hit'):return self.add_radiation()
        return super().hurt_world(damage) if label is None else super().hurt_world(damage,label)

    def defeat(self):
        # Preserve the existing game death/respawn flow with viable survival meters.
        self.survival.update(radiation=0,hunger=20,regen_remainder=0)
        return super().defeat()

    @classmethod
    def load(cls,path):
        game=super().load(path);game._init_survival()
        state=game.survival
        for key,low,high in [('radiation',0,100),('hunger',-20,20),('regen_remainder',0,30)]:
            value=state[key]
            if type(value) not in (int,float) or not math.isfinite(value) or not low<=value<=high:
                raise ValueError('Invalid survival040 state: '+key)
        if state['regen_remainder']>=30:raise ValueError('Invalid regeneration remainder')
        game.hp=min(game.hp,game.max_hp);game._sync_ap()
        return game
