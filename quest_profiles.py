"""Editable native quest variants and shared, deterministic reward formulas."""
import copy, math

def kind_of(q):return 'metro' if 'metro_city' in q else q['kind']
def defaults(kind,elite=False):
    import quest_catalog
    from game.catalog import BASE_REWARDS
    title,description={**quest_catalog.TYPES,**quest_catalog.SPECIAL}[kind]
    multiplier=2 if elite else 1
    return dict(title=title,description=description,art='quest:'+('recruit_tech' if kind=='recruit_mayor' else kind),
                min_level=1,reward=(0 if kind=='permit' else 100 if kind=='thanks' else BASE_REWARDS.get(kind,85))*multiplier,
                xp_reward=(0 if kind=='permit' else 70 if kind=='thanks' else 25)*multiplier,
                xp_step=(0 if kind=='permit' else 10 if kind=='thanks' else 5)*multiplier,money_power=1.3)

def profile(q,document=None):
    import quest_catalog
    document=quest_catalog.DOCUMENT if document is None else document
    return document.get('native',{}).get(kind_of(q),{}).get('elite' if q.get('unique') else 'normal')

def allowed(game,q):
    spec=q.get('authored_definition') or profile(q)
    return not spec or game.level>=spec.get('min_level',1)

def rewards(spec,level):
    level=max(1,level)
    return round(spec['reward']*level**spec.get('money_power',0)),round(spec['xp_reward']+spec.get('xp_step',0)*(level-1))

def validate(doc):
    import quest_catalog
    errors=[]
    native=doc.get('native',{})
    if not isinstance(native,dict):return ['Налаштування вбудованих квестів мають бути об’єктом.']
    for kind,variants in native.items():
        if kind not in {**quest_catalog.TYPES,**quest_catalog.SPECIAL} or not isinstance(variants,dict):
            errors.append('Невідомий тип квесту: '+str(kind));continue
        for variant,spec in variants.items():
            if variant not in ('normal','elite') or not isinstance(spec,dict):errors.append('Некоректний варіант квесту');continue
            errors+=validate_spec(spec,f'{kind}/{variant}: ')
    return errors

def validate_spec(spec,prefix=''):
    errors=[]
    for key in ('title','description','art'):
        if not isinstance(spec.get(key),str) or (key=='title' and not spec[key].strip()):errors.append(prefix+'Некоректне поле '+key)
    for key,low,high in [('min_level',1,100),('reward',0,10000000),('xp_reward',0,10000000),('xp_step',0,1000000)]:
        if type(spec.get(key)) is not int or not low<=spec[key]<=high:errors.append(prefix+'Некоректне поле '+key)
    power=spec.get('money_power')
    if type(power) not in (int,float) or not math.isfinite(power) or not 0<=power<=3:errors.append(prefix+'Степінь рівня має бути від 0 до 3')
    return errors

class QuestProfilesMixin:
    def apply_quest_profile(self,q):
        spec=profile(q)
        if not spec or q.get('authored_id'):return
        # Accepted quests retain the configuration copied at issue time.
        if q.get('status')!='offered' and q.get('quest_profile'):return
        from game.catalog import BASE_REWARDS
        from game.systems.reputation import reward_factor
        level=q.get('level',1)
        old_fee=round(BASE_REWARDS.get(q['kind'],0)*level**1.3*(2 if q.get('unique') else 1))
        compensation=q.get('_profile_compensation',max(0,q.get('base_reward',q.get('reward',0))-old_fee) if q['kind'] in ('supplies','trophies') else 0)
        q['_profile_compensation']=compensation
        money,xp=rewards(spec,level)
        q.update(title=spec['title'],quest_art=spec['art'],quest_description=spec['description'],
                 base_reward=money+compensation,reward=round((money+compensation)*reward_factor(self.reputation(q['city']))),
                 xp_reward=xp,quest_profile=copy.deepcopy(spec))

    def price_quest(self,q):
        if q.get('quest_profile') and q.get('status')!='offered':return
        super().price_quest(q)
        q.pop('_profile_compensation',None)
        self.apply_quest_profile(q)

    def mayor_offers(self):
        result=super().mayor_offers()
        for q in result:
            if q.get('status')=='offered':self.apply_quest_profile(q)
        return [q for q in result if allowed(self,q)]

    def accept_quest(self,ident):
        offer=next((q for q in self.mayor_offers() if q['id']==ident),None)
        if offer is None or not allowed(self,offer):return False
        return super().accept_quest(ident)

    def quest_text(self,q):
        text=super().quest_text(q)
        description=q.get('quest_description','')
        return description+'\n\n'+text if description else text

    def local_settlers(self):
        result=super().local_settlers()
        for settler in result:self.apply_quest_profile(settler['quest'])
        return [s for s in result if s['state']!='offered' or allowed(self,s['quest'])]

    def create_settler(self,role):
        if not allowed(self,dict(kind='recruit_'+role)):return None
        return super().create_settler(role)

    def check_border_quest(self):
        if not allowed(self,dict(kind='permit')):return
        before={q['id'] for q in self.quests}
        result=super().check_border_quest()
        for q in self.quests:
            if q['id'] not in before:self.apply_quest_profile(q)
        return result

    def check_thanks(self):
        if not allowed(self,dict(kind='thanks')):
            self.check_border_quest();return
        before={q['id'] for q in self.quests}
        result=super().check_thanks()
        for q in self.quests:
            if q['id'] not in before:self.apply_quest_profile(q)
        return result

    def turn_in(self,ident):
        q=next((q for q in self.quests if q['id']==ident),None)
        result=super().turn_in(ident)
        if result and q and q['kind']=='permit' and q.get('quest_profile'):
            self.money+=q['reward']
            if q['xp_reward']>0:self.gain_xp(self.quest_xp(q)*(2 if self.coward_turns else 1))
        return result
