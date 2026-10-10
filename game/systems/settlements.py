"""Settlement clearances, market specials and generator hazards."""
import math
from game.systems import frontier
from i18n import t as tr


class SettlementsMixin:
    def __init__(self,seed=None):
        """Ініціалізує об’єкт, його початковий стан і потрібні залежності."""
        super().__init__(seed);self.ensure_settlements()

    def clear_city_edges(self):
        """Прибирає гори й радіацію поблизу основних міст."""
        for cx,cy in self.cities[:self.main_city_count]:
            for y in range(max(0,cy-1),min(32,cy+2)):
                for x in range(max(0,cx-1),min(len(self.world[0]),cx+2)):
                    if self.world[y][x]=='cliff':self.world[y][x]='waste'
                    self.radiation.pop(f'{x},{y}',None)

    def ensure_settlements(self):
        """Забезпечує прохідні околиці міст і мерів на станціях метро."""
        self.clear_city_edges()
        for city in frontier.METRO_CITIES:
            if city not in self.mayors:self.mayors.append(city)

    def build_radiation(self):
        """Розподіляє радіаційні поля за географічними правилами."""
        super().build_radiation();self.clear_city_edges()

    def stock(self,merchant):
        """Повертає або оновлює асортимент торговця."""
        items=super().stock(merchant)
        city=self.trading_city(merchant)
        if city is None or self.reputation(city)<60:return items
        entry=self.traveler if merchant==3 or merchant==4 and self.traveler and self.traveler.get('hunter') else next((v for v in self.shops.values() if v['items'] is items),None)
        if entry is None or entry.get('special_checked'):return items
        entry['special_checked']=True
        pool=list(items)
        if pool and self.rng.random()<.25:
            item=self.rng.choice(pool)
            item['promotion']=dict(discount=self.rng.choices([30,50,75],[70,25,5])[0],city=city,merchant=merchant)
        return items

    def promotion(self,item,merchant):
        """Повертає діючу акційну знижку на товар."""
        sale=item.get('promotion') or {}
        city=self.trading_city(merchant)
        return sale.get('discount',0) if city is not None and self.reputation(city)>=60 and sale.get('city')==city and sale.get('merchant')==merchant else 0

    def price(self,item,merchant,buying=True):
        """Обчислює ціну купівлі або продажу предмета."""
        base=super().price(item,merchant,buying)
        if buying:return max(2,round(base*(1-self.promotion(item,merchant)/100)))
        # Includes discounts and paid-price cap, even after reputation or merchant changes.
        return max(1,min(base,self.price(item,merchant,True)-1,item.get('paid_sale_cap',base)))

    def prepare_purchase(self,item,merchant,unit_price):
        """Фіксує обмеження перепродажу акційного товару."""
        if not self.promotion(item,merchant):return
        def cap(obj):
            obj['paid_sale_cap']=max(1,min(obj.get('paid_sale_cap',unit_price-1),unit_price-1))
            obj.pop('promotion',None)
            if obj.get('contents'):cap(obj['contents'])
        cap(item)

    def welcomed(self,city):
        """Перевіряє, чи отримав гравець подяку від цього міста."""
        return city is not None and any(q['kind']=='thanks' and q['city']==city and q['status']=='done' for q in self.quests)

    def city_name(self,city):
        """Повертає назву міста з відповідними статусними позначками."""
        name=super().city_name(city)
        return '🏅 '+name if self.welcomed(city) else name

    def city_color(self,city,default='#e1e6d6'):
        """Обирає колір назви міста за статусом подяки."""
        return '#81db97' if self.welcomed(city) else default

    def quest_text(self,q):
        """Формує опис цілі, прогресу й винагороди завдання."""
        text=super().quest_text(q)
        if q['kind']=='hunt':text+='\n'+tr('update024.defense_radius')
        return text

    def generator_toggle(self,ident,index):
        """Перемикає рубильник, перевіряє порядок і застосовує наслідки помилки."""
        self._generator_shock=0
        q=self.local_expedition()
        wrong=bool(q and q['id']==ident and q['kind']=='generator' and type(index)==int and 0<=index<5 and len(q['generator_input'])<5 and index!=q['generator_order'][len(q['generator_input'])])
        ok=super().generator_toggle(ident,index)
        if ok and wrong and self.rng.random()<.35:
            self._generator_shock=self.rng.randint(1,5)
            self.hurt_world(self._generator_shock,tr('settlements.shock'))
        return ok

    @classmethod
    def load(cls,path):
        """Завантажує збереження та застосовує міграції цієї версії."""
        game=super().load(path);game.ensure_settlements();return game
