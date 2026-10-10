"""Battle feedback gameplay behavior."""


class BattleFeedbackMixin:
    def victory(self):
        b=self.battle
        result=super().victory()
        __import__('battle_results').finish(self,b,'Перемога')
        return result

    def flee(self):
        b=self.battle
        __import__('battle_results').begin(self)
        result=super().flee()
        if result:__import__('battle_results').finish(self,b,'Перемога' if b and b.get('cleared') else 'Відступ')
        return result

    def defeat(self):
        b=self.battle
        __import__('battle_results').begin(self)
        result=super().defeat()
        __import__('battle_results').finish(self,b,'Поразка')
        return result

    def search(self):
        b=self.battle
        __import__('battle_results').begin(self)
        result=super().search()
        __import__('battle_results').finish(self,b,'Перемога')
        return result

    def gain_xp(self,amount):
        __import__('battle_results').begin(self)
        return super().gain_xp(amount)
