import unittest
from types import SimpleNamespace
from unittest.mock import patch
from game.catalog import STAT_NAMES
from i18n import t as tr
from ui.item_inspection import summary, summary_color, GOOD, BAD, TEXT


class ItemSummaryTests(unittest.TestCase):
    def setUp(self):
        self.game=SimpleNamespace(weapon=None,equipped={})
        self.item=dict(id='test',name='Test',kind='module',rarity=0,level=1,
                       target='weapon',weight=1,value=10,
                       stats={'accuracy':5,'range':-1,'weight_percent':-10})

    def test_compatibility_is_first_and_universal(self):
        rows=summary(self.game,self.item)
        self.assertEqual(rows[0][:2],('Сумісна зброя','Універсальний'))
        self.assertNotIn('Сумісність',[r[0] for r in rows])
        for target,label in [('armor','Броня'),('helmet','Шоломи'),('protection','Універсальний')]:
            self.assertEqual(summary(self.game,dict(self.item,target=target))[0][:2],('Сумісна броня',label))

    def test_current_catalog_restrictions(self):
        with patch('ui.item_inspection.mr.restrictions',return_value={'target':'weapon','weapon_categories':['pistol','sniper']}):
            self.assertEqual(summary(self.game,self.item)[0][:2],('Сумісна зброя',', '.join(tr('update033.category_'+c) for c in ('pistol','sniper'))))

    def test_effect_colors_and_neutral_metadata(self):
        rows=summary(self.game,self.item)
        for stat,color in [('accuracy',GOOD),('range',BAD),('weight_percent',GOOD)]:
            row=next(r for r in rows if r[0]==STAT_NAMES[stat])
            self.assertEqual(summary_color(self.item,*row[:2]),color)
        for label in ('Вага','Вартість','Сумісна зброя'):
            row=next(r for r in rows if r[0]==label)
            self.assertEqual(summary_color(self.item,*row[:2]),TEXT)

    def test_food_benefit_and_damage(self):
        food=dict(self.item,kind='food',stats={},satiety=10,damage_percent=10)
        rows=summary(self.game,food)
        for label,color in [('Ситість',GOOD),('Шкода, % макс. HP',BAD)]:
            row=next(r for r in rows if r[0]==label)
            self.assertEqual(summary_color(food,*row[:2]),color)


if __name__=='__main__':unittest.main()
