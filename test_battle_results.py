import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import afterdays as r
import progression as p
import battle_results as results
import event_results


class BattleResultsTests(unittest.TestCase):
    def game(self):
        g=r.Game(47)
        g.battle=dict(w=10,h=10,walls=[],pos=[1,1],enemies=[],ap=6,max_ap=6,round=1,
                      corpses=[],kills=[],region_level=1,biome='waste',entrance047=[1,1])
        results.begin(g)
        return g

    def test_projectile_caps_overkill_and_records_before_kill(self):
        g=self.game();e=dict(id='enemy',hp=6,pos=[2,1],name='Enemy',awake=True)
        g.battle['enemies']=[e]
        with patch('combat033.projectile_components',return_value={'kinetic':10}),patch.object(g,'_finish_enemy'):
            g._projectile_damage(e,g.weapon,'single')
        self.assertEqual(g.battle['result_stats']['dealt'],6)

    def test_incoming_npc_combat_and_reflection(self):
        g=self.game();actor=dict(id='e',name='Enemy',hp=100,damage=7,range=1,pos=[2,1])
        player=dict(id='player',pos=[1,1]);target=dict(id='npc',name='NPC',hp=30,pos=[3,1])
        with patch.object(g.rng,'randrange',return_value=99),patch('update047.balance.damage',return_value=7),patch.object(g,'incoming_combat_damage',return_value=7),patch.object(g,'protection_stat',return_value=0):
            g.faction_attack(actor,player,True)
            g.faction_attack(actor,target,False)
        self.assertEqual(g.battle['result_stats']['received'],7)
        self.assertEqual(g.battle['result_stats']['dealt'],0)
        with patch.object(g.rng,'randrange',return_value=99),patch('update047.balance.damage',return_value=7),patch.object(g.rng,'random',return_value=0),patch.object(g,'protection_stat',side_effect=lambda k:100 if k=='reflect_percent' else 0):
            g.faction_attack(actor,player,True)
        self.assertEqual(g.battle['result_stats']['dealt'],7)
        self.assertEqual(g.battle['result_stats']['received'],7)

    def test_save_reload_preserves_stats_and_final_report_is_once(self):
        g=self.game();results.hit(g,'dealt',17,100);g.gain_xp(9)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'save.json';g.save(path);g=r.Game.load(path)
        b=g.battle;g.victory()
        self.assertEqual(len(g._event_results),1)
        states,items=event_results.groups(g._event_results[0])
        self.assertIn('17',states[0]['text']);self.assertIn('9 XP',states[2]['text'])
        results.finish(g,b,'Перемога');self.assertEqual(len(g._event_results),1)

    def test_old_loot_transfers_are_not_new_rewards(self):
        g=self.game();p.add_to(g.loot,p.parts(3));g.battle.pop('result_stats');results.begin(g)
        b=g.battle;g.battle=None
        self.assertTrue(g.collect(g.loot[0]['id']))
        before={i['id']:i.get('qty',1) for i in g.loot}
        p.add_to(g.loot,p.parts(2));results.capture_loot(g,b,before);results.finish(g,b,'Перемога')
        items=event_results.groups(g._event_results[0])[1]
        self.assertEqual(sum(row['item']['qty'] for row in items),2)

    def test_spent_ammo_does_not_hide_new_ammo_rewards(self):
        g=self.game();b=g.battle
        g.consume('ammo',20,'pistol')
        before={i['id']:i.get('qty',1) for i in g.loot}
        p.add_to(g.loot,p.ammunition('pistol',5));results.capture_loot(g,b,before)
        g.battle=None;g.collect(g.loot[0]['id']);results.finish(g,b,'Перемога')
        items=event_results.groups(g._event_results[0])[1]
        self.assertEqual(items[0]['item']['qty'],5)

    def test_retreat_and_defeat_report(self):
        for outcome in ('Відступ','Поразка'):
            g=self.game();results.hit(g,'received',10,100)
            if outcome=='Відступ':self.assertTrue(g.flee())
            else:g.defeat()
            self.assertEqual(g._event_results[0]['title'],outcome)
            self.assertIn('10',g._event_results[0]['rows'][1]['text'])

    def test_dungeon_reports_at_exit_not_when_cleared(self):
        g=self.game();b=g.battle;b.update(dungeon=True,cleared=False,exit=[1,1])
        g.victory();self.assertFalse(getattr(g,'_event_results',[]))
        b['pos']=b['exit'][:]
        self.assertTrue(g.flee());self.assertEqual(len(g._event_results),1)


if __name__=='__main__':unittest.main()
