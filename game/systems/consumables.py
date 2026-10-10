"""Editable, composable consumable effects shared by the game and content editor."""
from game import items as item_rules

import math
KINDS={'med':'Аптечка','food':'Їжа','rad':'Радіопротектор','repairkit':'Ремкомплект'}
EDITOR_KINDS={**KINDS,'credits':'Кредити'}
FIELDS={'value':('Ціна',0,1000000),'weight':('Вага',0,1000),'ap_cost':('Витрата ОД',0,100),
        'heal':('Лікування, HP',0,10000),'heal_percent':('Лікування, % макс. HP',0,100),
        'satiety':('Ситість',0,40),'radiation_heal':('Зняття радіації, %',0,100),
        'repair':('Відновлення стану спорядження',0,100),'regen':('Регенерація, HP',0,1000),
        'regen_duration':('Регенерація, кроків',0,1000000),'satiety_duration':('Обжертість, кроків',0,1000000),
        'stealth_duration':('Непомітність, кроків',0,1000000)}
FIELDS['damage_percent']=('Шкода, % макс. HP',0,100)
DEFAULTS={key:0 for key in FIELDS};DEFAULTS['ap_cost']=2
LEGACY={'med':dict(heal_percent=50),'food':dict(satiety=10),'rad':dict(radiation_heal=50),'repairkit':dict(repair=35)}

def definition(item):
    import content
    value=dict(DEFAULTS,**LEGACY.get(item['kind'],{}))
    value.update(content.CONSUMABLES.get(item.get('type_id','item_'+item['kind']),{}))
    value.update({k:v for k,v in item.items() if k in FIELDS})
    return value

def validate(data,art):
    errors=[]
    for ident,value in data.items():
        if value.get('kind') not in EDITOR_KINDS:continue
        if not value.get('name','').strip():errors.append(ident+': потрібна назва.')
        if value.get('sprite_id') not in art and not (value['kind']=='credits' and not value.get('sprite_id')):errors.append(ident+': невідомий арт.')
        if value['kind']=='credits':
            if ident!='item_credits' or value.get('weight')!=0 or value.get('value')!=1:errors.append(ident+': кредити мають вагу 0 і номінал 1.')
            continue
        for key,(_,low,high) in FIELDS.items():
            n=value.get(key,DEFAULTS[key])
            if type(n) not in (int,float) or not math.isfinite(n) or not low<=n<=high or (key not in ('weight','heal_percent') and type(n) is not int):errors.append(ident+': некоректне поле '+key)
    return errors


class Consumables:
    def consumable_candidate(self,token):
        items=[i for i in self.bag if (i['id']==token or i['kind']==token) and i['kind'] in KINDS and not i.get('quest_id') and i.get('qty',1)>0]
        return next((i for i in items if self.consumable_useful(i)),None)

    def consumable_useful(self,item):
        d=definition(item)
        return bool(((d['heal'] or d['heal_percent']) and self.hp<self.max_hp) or
                    (d['satiety'] and self.hunger<20) or (d['radiation_heal'] and self.radiation_injury>0) or
                    d['regen_duration'] or d['satiety_duration'] or d['stealth_duration'] or d['damage_percent'])

    def can_use_consumable(self,token):
        item=self.consumable_candidate(token)
        return bool(item and (not self.battle or self.battle['ap']>=definition(item)['ap_cost']))

    def apply_consumable(self,item,automatic=False,target=None):
        
        import module_rules
        d=definition(item)
        if self.battle and not automatic and self.battle['ap']<d['ap_cost']:return False
        if target is None and not self.consumable_useful(item):return False
        item_rules.extract(self.bag,item,1)
        if self.battle and not automatic:self.battle['ap']-=d['ap_cost']
        if d['radiation_heal']:self.cure_radiation(d['radiation_heal'])
        if d['heal'] or d['heal_percent']:self.regenerate(d['heal']+math.ceil(self.max_hp*d['heal_percent']/100))
        if d['satiety']:self.change_satiety(d['satiety'])
        if target is not None:
            before=module_rules.condition(target);target['durability']=min(module_rules.max_condition(target),before+d['repair'])
            self.emit(f"{target['name']}: стан +{target['durability']-before:g}",color='#9cdda8')
        for kind,duration,amount in [('buff_regen',d['regen_duration'],d['regen']),('buff_satiety',d['satiety_duration'],0),('buff_stealth',d['stealth_duration'],0)]:
            if duration:self.add_buff(kind,duration,amount)
        self.hp=min(self.hp,self.max_hp);self._sync_ap()
        if d['damage_percent']:self.hurt_world(math.ceil(self.max_hp*d['damage_percent']/100),item['name'])
        return True

    def use(self,token):
        item=self.consumable_candidate(token)
        if item:return self.apply_consumable(item)
        # Known consumables that cannot help must not fall through to legacy hardcoded effects.
        if token in KINDS or any(i['id']==token and i['kind'] in KINDS for i in self.bag):return False
        return super().use(token)

    def eat(self,automatic=False):
        foods=[i for i in self.bag if i['kind']=='food' and not i.get('quest_id') and i.get('qty',1)>0 and definition(i)['satiety']>0 and (not automatic or not definition(i)['damage_percent'])]
        item=min(foods,key=lambda i:(i.get('rarity',0),definition(i)['satiety'],i.get('value',0)),default=None)
        if not item or self.hunger>=20 or definition(item)['satiety']<=0:return False
        return self.apply_consumable(item,automatic=automatic)

    def repair_kit(self,ident=None):
        return next((i for i in self.bag if i['kind']=='repairkit' and not i.get('quest_id') and i.get('qty',1)>0 and definition(i)['repair']>0 and (ident is None or i['id']==ident)),None)

    def can_repair_with_kit(self,item):
        return bool(self.repair_kit() and super().can_repair_with_kit(item))

    def repair_with_kit(self,ident,kit_id=None):
        import module_rules
        target=self.find(ident)
        kit=self.repair_kit(kit_id)
        if not self.can_repair_with_kit(target) or not kit or not target or not (target['kind'] in ('weapon','armor','helmet') or target.get('quest_repair')) or module_rules.condition(target)>=module_rules.max_condition(target):return False
        return self.apply_consumable(kit,target=target)
