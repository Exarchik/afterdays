"""Fresh-process checks: editor startup must not depend on prior game imports."""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parent

class FactionImportTests(unittest.TestCase):
    def run_fresh(self,code):
        result=subprocess.run([sys.executable,'-B','-X','utf8','-c',code],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_preview_without_game_preimport(self):
        self.run_fresh("import faction_rules as f, random; e=f.make_human(random.Random(47),'human_bandit','bandits',1,[0,0]); assert e['equipment']['weapon']; assert e['hp']>0")

    def test_loot_without_game_preimport(self):
        self.run_fresh("import faction_rules as f, random; assert isinstance(f.human_loot(random.Random(47),{'equipment':{},'level':1}),list)")

if __name__=='__main__':unittest.main()
