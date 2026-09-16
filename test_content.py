import copy,json,re,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import afterdays as r
import progression as p
import content,i18n,sprites,balance
ROOT=Path(__file__).resolve().parent
class ContentTests(unittest.TestCase):
 def test_ids_and_all_factory_models(self):
  for key,value in content.EQUIPMENT.items():
   self.assertRegex(key,r'^[a-z][a-z0-9_]+$')
   item=p.equipment(key,level=value['min_level'])
   self.assertEqual(item['type_id'],key);self.assertEqual(item['name'],content.name(key))
   self.assertIn(sprites.item_key(item),sprites.MANIFEST)
  for key in content.MODULE_DATA:
   item=p.module(index=key);self.assertEqual(item['type_id'],key)
  for key in content.MONSTER_DATA:
   e=dict(kind=key,level=1,grade='normal');balance.set_monster(e)
   self.assertEqual(e['type_id'],key);self.assertIn(key,sprites.MANIFEST)
 def test_renaming_does_not_change_stats_or_sprite(self):
  key='weapon_ash_pistol';a=p.equipment(key,level=3);sprite=sprites.item_key(a)
  with patch.dict(i18n.TRANSLATIONS,{key+'.name':'Test renamed weapon',key+'.description':'Custom description'}):
   b=p.equipment(key,level=3);self.assertEqual(b['name'],'Test renamed weapon')
   self.assertEqual(a['stats'],b['stats']);self.assertEqual(sprite,sprites.item_key(b))
   content.identify_item(a);self.assertEqual(a['name'],b['name'])
   from refinement_ui import description
   self.assertIn('Custom description',description(r.Game(4),b))
 def test_legacy_item_migration_preserves_state(self):
  g=r.Game(12);item=p.equipment('Пістолет «Попіл»',tier=2,level=4);item['durability']=31
  mod=p.module(index=0,level=4);item['modules']=[mod]
  item.pop('type_id');mod.pop('type_id');g.bag.append(item)
  before=copy.deepcopy(item);state=g.rng.getstate();content.migrate(g)
  for key in ('id','stats','durability','level','rarity','value'):self.assertEqual(before[key],item[key])
  self.assertEqual(g.rng.getstate(),state);self.assertEqual(item['type_id'],'weapon_ash_pistol')
  self.assertEqual(mod['type_id'],'module_amplifier')
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'save.json';g.save(path);other=r.Game.load(path)
   self.assertEqual(g.bag,other.bag);self.assertEqual(g.rng.getstate(),other.rng.getstate())
 def test_legacy_names_are_input_aliases(self):
  for old,key in content.ALIASES['gear'].items():
   self.assertEqual(content.GEAR[old],content.GEAR[key]);self.assertEqual(p.equipment(old,level=30)['type_id'],key)
 def test_missing_language_key_and_bad_template_fall_back(self):
  key=next(k for k,v in i18n.FALLBACK.items() if '{v0}' in v and '{v1' not in v and '{v2' not in v)
  with patch.object(i18n,'TRANSLATIONS',{}):self.assertEqual(i18n.t('weapon_ash_pistol.name'),i18n.FALLBACK['weapon_ash_pistol.name'])
  with patch.dict(i18n.TRANSLATIONS,{key:'Invalid {missing}'}):self.assertEqual(i18n.t(key,v0='X'),i18n.FALLBACK[key].format(v0='X'))
 def test_monster_order_independent_lookup(self):
  before={key:content.MONSTERS[key] for key in content.MONSTER_DATA}
  with patch.object(content,'MONSTER_DATA',dict(reversed(list(content.MONSTER_DATA.items())))):
   for key,value in before.items():self.assertEqual(content.MONSTERS[key],value)
 def test_genuine_v0151_fixture(self):
  path=ROOT/'tests_fixtures/save_v0151.json';old=json.loads(path.read_text());g=r.Game.load(path)
  for key in ('world','cities','xp','money','turn','hp'):self.assertEqual(getattr(g,key),old[key])
  for slot,item in g.equipped.items():
   if item:
    self.assertIn(item['type_id'],content.EQUIPMENT)
    for key in ('id','stats','durability','level','rarity','value'):self.assertEqual(item[key],old['equipped'][slot][key])
