"""Rest checkpoints and persistent, capacity-aware recovery of carried belongings."""
import module_rules

import math
import uuid


class Recovery:
    @property
    def respawn_pos(self):return self.reputation_state.get('respawn047',self.cities[0])[:]

    @property
    def graves(self):return self.reputation_state.setdefault('graves047',[])

    def local_graves(self):return [g for g in self.graves if g['pos']==[self.x,self.y]]

    def rest(self):
        result=super().rest()
        if result:
            self.reputation_state['respawn047']=[self.x,self.y]
            self.log('Точку відродження оновлено. На мапі її позначено зеленим прапорцем.')
        return result

    def defeat(self):
        
        from game.systems.credits import credit_item
        position=[self.x,self.y];checkpoint=self.respawn_pos;kept=[];dropped=[];credits=0
        for item in self.bag:
            if item['kind']=='credits':credits+=item.get('qty',1)
            elif item['kind'] in ('ammo','parts','fragments','quest') or item.get('quest_id') or item.get('quest_repair') or item.get('field_test'):kept.append(item)
            else:dropped.append(item)
        saved_credits=credits*70//100
        if saved_credits:dropped.append(credit_item(saved_credits))
        self.graves.append(dict(id=uuid.uuid4().hex,pos=position,items=dropped,turn=self.turn))
        self.bag=kept
        for item in self.equipped.values():
            if item and 'durability' in item:item['durability']=round(module_rules.condition(item)*.5,2)
        self._grave_death=True
        try:super().defeat()
        finally:self._grave_death=False
        self.x,self.y=checkpoint
        self.hp=max(1,math.ceil(self.max_hp*.25))
        self.reveal(self.x,self.y,2)
        self.log(f'Відродження: {self.x};{self.y}, 25% здоров’я. Речі й {saved_credits} кр. залишилися в надгробку {position[0]};{position[1]}. Втрачено {credits-saved_credits} кр.; міцність екіпіровки зменшено вдвічі.')

    def search(self):
        if not self.battle and not self.road_event and self.local_graves():
            self._grave_request=True;return True
        return super().search()

    def collect_grave(self,grave_id,item_id):
        if self.battle or self.road_event:return False
        grave=next((g for g in self.local_graves() if g['id']==grave_id),None)
        if not grave:return False
        previous=self.loot
        self.loot=grave['items']
        try:result=self.collect(item_id)
        finally:self.loot=previous
        # The legacy collector copies a partial stack's ID into the bag.
        # Give the remainder a fresh ID before a later death creates another grave.
        if result:
            remainder=next((i for i in grave['items'] if i['id']==item_id),None)
            if remainder:remainder['id']=uuid.uuid4().hex
        if not grave['items']:self.graves.remove(grave)
        return result

    def collect_all_graves(self):
        if self.battle or self.road_event:return False
        result=False
        for grave in list(self.local_graves()):
            if not grave['items']:self.graves.remove(grave);continue
            for item in list(grave['items']):result=self.collect_grave(grave['id'],item['id']) or result
        return result

    @classmethod
    def load(cls,path):
        game=super().load(path)
        import content
        pos=game.respawn_pos
        if len(pos)!=2 or any(type(n) is not int for n in pos) or not game.passable(*pos):raise ValueError('Некоректна точка відродження.')
        for grave in game.graves:
            pos=grave['pos']
            if len(pos)!=2 or any(type(n) is not int for n in pos) or not game.passable(*pos):raise ValueError('Некоректне розташування надгробка.')
            for item in grave['items']:content.identify_item(item)
        return game
