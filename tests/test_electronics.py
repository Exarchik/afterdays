"""Circuit-board repair: contact pads instead of outlines, per-quest contacts, decoys, sparks."""
import copy
import tempfile
import unittest
from pathlib import Path

import circuit_art
import quest_catalog
import quest_minigames
import quest_profiles
from game.model import Game
from game.systems import electronics as el
from tests.fixtures.quest_offer import offer_for


def accepted(seed=4):
    g=Game(seed);offer=offer_for(g,el.KIND)
    assert g.accept_quest(offer['id'])
    q=g.electronics_quest(offer['id']);g.x,g.y=q['pos']
    return g,q


def install(g,q,skip=()):
    for i,p in enumerate(q['circuit_target']):
        if i in skip:continue
        q['circuit_rotations'][str(p)]=q['circuit_angles'][i]
        assert g.place_circuit(q['id'],p,i)


class ElectronicsTests(unittest.TestCase):
    def test_defaults_validation_and_editor_block(self):
        spec=quest_profiles.defaults(el.KIND)
        self.assertEqual(el.settings_for(spec),{'contacts_min':3,'contacts_max':5,'decoys':1,'hints':1,'shock':0})
        self.assertEqual(quest_profiles.validate_spec(spec),[])
        self.assertEqual([k for k,_ in quest_minigames.MINIGAMES[el.KIND]['fields']],list(el.SETTINGS))
        self.assertEqual(len(el.validate_settings(dict(spec,decoys=9,shock='x'))),2)
        self.assertEqual(len(el.validate_settings(dict(spec,contacts_min=5,contacts_max=4))),1)

    def test_board_has_decoys_and_per_quest_contacts_on_the_module_edge(self):
        g,q=accepted()
        self.assertEqual(q['circuit_version'],el.VERSION)
        self.assertEqual(len(q['circuit_inventory']),el.SLOTS+1)
        self.assertEqual(set(q['circuit_target'])|set(q['circuit_inventory']),set(q['circuit_inventory']))
        for piece in q['circuit_inventory']:
            contacts=q['circuit_contacts'][str(piece)]
            self.assertTrue(3<=len(contacts)<=5)
            alpha=circuit_art.tile(piece).getchannel('A')
            for x,y in contacts:
                self.assertTrue(0<x<circuit_art.TILE and 0<y<circuit_art.TILE)
                # Each contact sits just outside the visible art, next to an opaque pixel.
                near=[alpha.getpixel((min(149,max(0,x+dx)),min(149,max(0,y+dy)))) for dx in range(-4,5) for dy in range(-4,5)]
                self.assertGreater(max(near),180)
        h=Game(4);h.quests.append(copy.deepcopy(q));q2=h.quests[-1];q2['circuit_version']=0
        h.init_circuit_board(q2);self.assertEqual(q2['circuit_contacts'],q['circuit_contacts'])
        g2,other=accepted(7)
        self.assertNotEqual(other['circuit_contacts'],q['circuit_contacts'])

    def test_correct_installation_powers_up(self):
        g,q=accepted();install(g,q)
        self.assertEqual(g.circuit_faults(q),[])
        hp=g.hp;self.assertTrue(g.check_circuits(q['id']))
        self.assertTrue(q['circuit_checked']);self.assertTrue(g.quest_ready(q));self.assertEqual(g.hp,hp)
        self.assertFalse(g.place_circuit(q['id'],q['circuit_target'][0],None))

    def test_wrong_rotation_or_decoy_sparks_without_failing(self):
        g,q=accepted();install(g,q)
        piece=q['circuit_target'][2];q['circuit_rotations'][str(piece)]=(q['circuit_angles'][2]+2)%4
        hp=g.hp
        self.assertFalse(g.check_circuits(q['id']));self.assertEqual(q['circuit_bad'],[2]);self.assertEqual(g.hp,hp)
        self.assertFalse(g.circuit_fit(q,piece,2)['ok'])
        self.assertTrue(g.rotate_circuit(q['id'],piece));self.assertEqual(q['circuit_bad'],[])
        decoy=next(p for p in q['circuit_inventory'] if p not in q['circuit_target'])
        g.rotate_circuit(q['id'],piece);g.place_circuit(q['id'],decoy,2)
        self.assertNotIn(piece,q['circuit_slots'])
        self.assertFalse(g.check_circuits(q['id']));self.assertEqual(q['circuit_bad'],[2])
        g.place_circuit(q['id'],piece,2);self.assertTrue(g.check_circuits(q['id']))

    def test_live_fit_marks_pads_and_contact_one(self):
        g,q=accepted();piece=q['circuit_target'][0]
        q['circuit_rotations'][str(piece)]=q['circuit_angles'][0]
        info=g.circuit_fit(q,piece,0)
        self.assertTrue(info['ok'] and info['pin1'] and all(info['pads']) and all(info['contacts']))
        wrong=[g.circuit_fit(q,piece,0) for _ in range(3) if g.rotate_circuit(q['id'],piece)]
        self.assertTrue(all(not w['ok'] for w in wrong))

    def test_optional_shock_never_kills(self):
        g,q=accepted();q['circuit_settings']['shock']=5;install(g,q,skip=(0,))
        decoy=next(p for p in q['circuit_inventory'] if p not in q['circuit_target'])
        g.place_circuit(q['id'],decoy,0);g.hp=3
        self.assertFalse(g.check_circuits(q['id']));self.assertEqual(g.hp,1)

    def test_editor_profile_controls_board(self):
        g=Game(4);offer=offer_for(g,el.KIND)
        spec=dict(quest_profiles.defaults(el.KIND),contacts_min=4,contacts_max=4,decoys=0)
        doc=copy.deepcopy(quest_catalog.DOCUMENT);doc.setdefault('native',{})[el.KIND]={'normal':spec,'elite':spec}
        old=quest_catalog.DOCUMENT;quest_catalog.DOCUMENT=doc
        try:self.assertTrue(g.accept_quest(offer['id']))
        finally:quest_catalog.DOCUMENT=old
        q=g.quests[-1]
        self.assertEqual(len(q['circuit_inventory']),el.SLOTS)
        self.assertTrue(all(len(c)==4 for c in q['circuit_contacts'].values()))

    def test_only_editable_at_the_repair_site(self):
        g,q=accepted();g.x,g.y=g.cities[q['city']]
        self.assertFalse(g.place_circuit(q['id'],q['circuit_target'][0],0))
        self.assertFalse(g.rotate_circuit(q['id'],q['circuit_target'][0]))
        self.assertFalse(g.check_circuits(q['id']))

    def test_old_saves_upgrade(self):
        g,q=accepted()
        old=dict(q);[old.pop(k) for k in ('circuit_contacts','circuit_settings','circuit_bad')]
        old['circuit_version']=2;old['circuit_inventory']=old['circuit_target'][:]
        old['circuit_rotations']={str(p):0 for p in old['circuit_target']}
        old['circuit_slots']=[old['circuit_target'][0]]+[None]*5
        done=dict(copy.deepcopy(old),id=old['id']+'x',circuit_checked=True,progress=1,circuit_slots=old['circuit_target'][:])
        g.quests[-1:]=[old,done];g.migrate_circuit_quests()
        for item in (old,done):self.assertEqual(item['circuit_version'],el.VERSION)
        self.assertEqual(old['circuit_slots'][0],old['circuit_target'][0])
        self.assertEqual(old['circuit_rotations'][str(old['circuit_target'][0])],0)
        self.assertTrue(g.quest_ready(done));self.assertEqual(len(done['circuit_inventory']),el.SLOTS)

    def test_state_survives_save(self):
        g,q=accepted();install(g,q,skip=(5,))
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'save.json';g.save(path);h=Game.load(path)
        self.assertEqual(next(x for x in h.quests if x['id']==q['id']),q)


if __name__=='__main__':unittest.main()
