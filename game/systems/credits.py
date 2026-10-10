"""Credits gameplay behavior."""
from game import catalog as game_catalog
from game import items as item_rules

def credit_item(qty):
    import content
    return dict(id=game_catalog.uid(),type_id='item_credits',kind='credits',name=content.CONSUMABLES['item_credits']['name'],qty=qty,weight=0,value=1,rarity=0,level=1)


class CreditsMixin:
    def __init__(self,*args,**kwargs):
        self._physical_credits_ready=False
        super().__init__(*args,**kwargs)
        amount=self.__dict__.get('money',0);self._physical_credits_ready=True
        if amount:item_rules.add_to(self.bag,credit_item(amount))

    @property
    def carried_money(self):return sum(i.get('qty',1) for i in self.bag if i['kind']=='credits')

    @property
    def stored_money(self):return sum(i.get('qty',1) for i in self.stash if i['kind']=='credits')

    @property
    def money(self):
        if not getattr(self,'_physical_credits_ready',False):return self.__dict__.get('money',0)
        return self.carried_money+self.stored_money

    @money.setter
    def money(self,value):
        value=max(0,int(value))
        if getattr(self,'_physical_credits_ready',False):
            difference=value-self.money
            if difference>0:item_rules.add_to(self.bag,credit_item(difference))
            elif difference<0:
                remaining=-difference
                for source in (self.bag,self.stash):
                    for item in list(source):
                        if item['kind']!='credits':continue
                        count=min(remaining,item.get('qty',1));item_rules.extract(source,item,count);remaining-=count
                        if not remaining:break
                    if not remaining:break
        self.__dict__['money']=value

    def save(self,path):
        self.__dict__['money']=self.money
        return super().save(path)

    @classmethod
    def load(cls,path):
        game=super().load(path)
        stacks=[i for i in game.bag+game.stash if i['kind']=='credits']
        if any(type(i.get('qty')) is not int or i['qty']<1 for i in stacks):raise ValueError('Invalid credit stack')
        if not stacks and game.__dict__.get('money',0)>0:item_rules.add_to(game.bag,credit_item(game.__dict__['money']))
        game.__dict__['money']=game.money
        return game

    def buys_kind(self,item,merchant):
        if item['kind']=='credits':return False
        return super().buys_kind(item,merchant)
