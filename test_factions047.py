import copy
import json
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import game.model as afterdays
import content
import entity_catalog
import faction_rules as rules
import monster_rules
import module_rules


class FactionTests(unittest.TestCase):
    def game(self):
        g=afterdays.Game(47)
        g.battle=dict(w=10,h=10,walls=[],pos=[1,1],enemies=[],ap=g.max_ap,max_ap=g.max_ap,round=1,corpses=[],kills=[],region_level=1,entrance047=[1,1])
        return g

    def human(self,faction='bandits',pos=(4,4),level=1):
        return rules.make_human(random.Random(1),'human_settler' if faction=='settlers' else 'human_bandit',faction,level,pos)

    def test_relationship_matrix(self):
        for f in ('bandits','monsters','infected'):self.assertTrue(rules.hostile('player',f))
        self.assertFalse(rules.hostile('settlers','player'))
        for a in rules.catalog()['factions']:
            for b in rules.catalog()['factions']:
                self.assertEqual(rules.hostile(a,b),a!=b or a=='infected')

    def test_equipment_levels_and_modules(self):
        seen=0
        doc=copy.deepcopy(rules.catalog());doc['humans']['human_bandit']['module_chance']=100
        for level in (1,2,5,10):
            for seed in range(20):
                e=rules.make_human(random.Random(seed),'human_bandit','bandits',level,[1,1],doc)
                self.assertIn('weapon',e['equipment'])
                for item in e['equipment'].values():
                    self.assertLessEqual(item['level'],level);self.assertLessEqual(content.EQUIPMENT[item['type_id']]['min_level'],level)
                    for mod in item['modules']:
                        seen+=1;self.assertTrue(module_rules.compatible(item,mod));self.assertLessEqual(mod['level'],level)
        self.assertGreater(seen,0)

    def test_drop_threshold_each_item_and_no_trophy(self):
        e=self.human();rng=random.Random(7)
        with patch.object(rng,'random',return_value=.249999):drops=rules.human_loot(rng,e)
        self.assertEqual({i['id'] for i in drops if i['kind'] in ('weapon','armor','helmet')},{i['id'] for i in e['equipment'].values()})
        self.assertTrue(any(i['kind']=='credits' for i in drops));self.assertFalse(any(i['kind']=='trophy' for i in drops))
        with patch.object(rng,'random',return_value=.25):drops=rules.human_loot(rng,e)
        self.assertFalse(any(i['kind'] in ('weapon','armor','helmet') for i in drops))
        values=iter([.8 if n==1 else .1 for n in range(len(e['equipment']))]+[.99]*5)
        with patch.object(rng,'random',side_effect=lambda:next(values)):drops=rules.human_loot(rng,e)
        self.assertEqual([i['id'] for i in drops],[i['id'] for n,i in enumerate(e['equipment'].values()) if n!=1])

    def test_bandit_prefers_nearby_monster(self):
        g=self.game();bandit=self.human(pos=(6,6));monster=monster_rules.make(random.Random(1),0,1,[6,5]);monster['faction']='monsters'
        g.battle['enemies']=[bandit,monster]
        with patch.object(g,'faction_attack') as attack:g.end_turn()
        self.assertIs(attack.call_args_list[0].args[1],monster)

    def test_infected_attack_same_faction(self):
        g=self.game();actors=[monster_rules.make(random.Random(n),0,1,pos) for n,pos in enumerate(([6,6],[6,5]))]
        for e in actors:e.update(faction='infected',range=1)
        g.battle['enemies']=actors
        with patch.object(g,'faction_attack') as attack:g.end_turn()
        self.assertIs(attack.call_args_list[0].args[1],actors[1])

    def test_allies_never_target_player_or_receive_direct_shot(self):
        g=self.game();ally=self.human('settlers',(3,3));bandit=self.human(pos=(3,4));g.battle['enemies']=[ally,bandit]
        before=(g.battle['ap'],g.count('ammo',g.weapon['ammo_type']))
        self.assertFalse(g.shoot(ally['id']));self.assertEqual(before,(g.battle['ap'],g.count('ammo',g.weapon['ammo_type'])))
        with patch.object(g,'faction_attack') as attack:g.end_turn()
        ally_attack=next(c for c in attack.call_args_list if c.args[0] is ally)
        self.assertIs(ally_attack.args[1],bandit);self.assertFalse(ally_attack.args[2])

    def test_safe_exit_collects_human_drops_once(self):
        g=self.game();ally=self.human('settlers');enemy=self.human();g.battle['enemies']=[ally,enemy]
        item=copy.deepcopy(enemy['equipment']['weapon'])
        with patch('faction_rules.human_loot',return_value=[item]):g._finish_enemy(enemy)
        g.check_faction_victory();self.assertTrue(g.battle['safe_exit047']);self.assertNotIn(item,g.loot)
        self.assertFalse(g.flee());self.assertEqual(g.coward_turns,0)
        self.assertTrue(g.battle_move(g.battle['exit']));self.assertIsNone(g.battle);self.assertEqual(g.coward_turns,0)
        self.assertEqual(sum(i['id']==item['id'] for i in g.loot),1);self.assertFalse(any(i['kind']=='trophy' for i in g.loot))
        self.assertFalse(g.flee())

    def test_hostile_retreat_keeps_penalty(self):
        g=self.game();g.battle['enemies']=[self.human()]
        self.assertTrue(g.flee());self.assertEqual(g.coward_turns,50)

    def test_friendly_encounter_without_kills_has_no_free_loot(self):
        g=self.game();g.battle['enemies']=[self.human('settlers')];money=g.money;loot=copy.deepcopy(g.loot)
        g.check_faction_victory();self.assertTrue(g.battle_move(g.battle['exit']));self.assertIsNone(g.battle)
        self.assertEqual(g.money,money);self.assertEqual(g.loot,loot)

    def test_dungeon_with_surviving_friend_safe_exit(self):
        g=self.game();g.battle.update(dungeon=True,cleared=False,exit=[1,1],chest=[8,8],chest_open=False)
        g.battle['enemies']=[self.human('settlers')]
        g.check_faction_victory();self.assertTrue(g.battle_move(g.battle['exit']));self.assertIsNone(g.battle);self.assertEqual(g.coward_turns,0)

    def test_npc_kill_has_loot_without_player_xp(self):
        g=self.game();killer=self.human('settlers');victim=self.human();g.battle['enemies']=[killer,victim];victim['hp']=1
        before=g.xp
        with patch.object(g.rng,'randrange',return_value=50):g.faction_attack(killer,victim,False)
        self.assertNotIn(victim,g.battle['enemies']);self.assertEqual(g.xp,before);self.assertEqual(len(g.battle['kills']),1)

    def test_save_load_humans_and_pending_loot(self):
        g=self.game();g.battle['enemies']=[self.human('settlers'),self.human()]
        g._finish_enemy(g.battle['enemies'][1]);g.check_faction_victory()
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'game.json';g.save(path);state=g.rng.getstate();loaded=afterdays.Game.load(path)
            self.assertEqual(g.battle,loaded.battle);self.assertEqual(state,loaded.rng.getstate())
            self.assertTrue(loaded.battle_move(loaded.battle['exit']));self.assertIsNone(loaded.battle);self.assertEqual(loaded.coward_turns,0)

    def test_catalog_validation(self):
        store=entity_catalog.Store();self.assertEqual(rules.validate(store.data['factions'],store.data['monsters'],store.art),[])
        doc=copy.deepcopy(store.data['factions']);doc['factions']['bandits']['relations']['settlers']='friendly'
        self.assertTrue(rules.validate(doc,store.data['monsters'],store.art))
        doc=copy.deepcopy(store.data['factions']);doc['humans']['human_bandit']['min_level']=0
        self.assertTrue(rules.validate(doc,store.data['monsters'],store.art))

    def test_ambient_generation_contains_humans_and_factions(self):
        g=self.game();seen=set()
        for _ in range(40):
            g.start_battle()
            for e in g.battle['enemies']:
                seen.add(e['faction'])
                if e.get('human'):self.assertLessEqual(e['level'],g.battle['region_level'])
        self.assertTrue({'bandits','settlers','monsters','infected'}<=seen)


if __name__=='__main__':unittest.main()
