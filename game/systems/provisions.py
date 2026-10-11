"""Three carried food stacks, consumed in the player's chosen order."""
from game import items
from game.systems.consumables import definition


class ProvisionsMixin:
    def __init__(self, *args, **kwargs):
        self.provisions = []
        super().__init__(*args, **kwargs)

    @property
    def weight(self):
        return round(super().weight + sum(items.item_weight(i) for i in self.provisions), 2)

    def find(self, ident):
        return next((i for i in self.provisions if i['id'] == ident), None) or super().find(ident)

    def pack_provision(self, ident, slot=2, qty=None):
        if self.battle or type(slot) is not int or not 0 <= slot < 3:
            return False
        old = next((n for n, i in enumerate(self.provisions) if i['id'] == ident), None)
        if old is not None:
            item = self.provisions.pop(old)
            self.provisions.insert(min(slot, len(self.provisions)), item)
            return True
        item = next((i for i in self.bag if i['id'] == ident), None)
        if not item or item['kind'] != 'food' or item.get('quest_id') or definition(item)['satiety'] <= 0:
            return False
        amount = item.get('qty', 1) if qty is None else qty
        if type(amount) is not int or not 1 <= amount <= item.get('qty', 1):
            return False
        target = self.provisions[slot] if slot < len(self.provisions) else None
        moved = items.extract(self.bag, item, amount)
        if target and items.stack_key(target) == items.stack_key(item):
            target['qty'] = target.get('qty', 1) + moved.get('qty', 1)
        else:
            if target:
                self.provisions[slot] = moved
                items.add_to(self.bag, target)
            else:
                self.provisions.append(moved)
        return True

    def unpack_provision(self, ident):
        if self.battle:
            return False
        item = next((i for i in self.provisions if i['id'] == ident), None)
        if item is None:
            return False
        self.provisions.remove(item)
        items.add_to(self.bag, item)
        return True

    def eat(self, automatic=False):
        if not automatic:
            return super().eat(automatic=False)
        if not self.provisions or self.hunger >= 20:
            return False
        item = self.provisions[0]
        if definition(item)['satiety'] <= 0:
            return False
        return self.apply_consumable(item, automatic=True, source=self.provisions)

    def defeat(self):
        # Food on the belt follows the same grave rules as carried food.
        for item in self.provisions:
            items.add_to(self.bag, item)
        self.provisions = []
        return super().defeat()

    @classmethod
    def load(cls, path):
        game = super().load(path)
        queue = game.provisions
        if not isinstance(queue, list) or len(queue) > 3:
            raise ValueError('Invalid provisions')
        ids = {i['id'] for i in game.bag}
        for item in queue:
            if (not isinstance(item, dict) or item.get('kind') != 'food'
                    or item.get('quest_id') or not isinstance(item.get('id'), str)
                    or item['id'] in ids or type(item.get('qty', 1)) is not int
                    or item.get('qty', 1) < 1):
                raise ValueError('Invalid provision item')
            ids.add(item['id'])
        return game
