import copy
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from PIL import Image
import custom_atlases as atlas
from art_library import encode


class AtlasTests(unittest.TestCase):
    def test_multiple_pages_aliases_and_exact_alpha(self):
        with tempfile.TemporaryDirectory() as folder:
            store=SimpleNamespace(root=Path(folder),data={'sprites':{}},baseline={'sprites':{}},pending_assets={})
            for n in range(65):
                prefix=f'custom/test_{n}'
                store.data['sprites'][str(n)]=dict(sheet=prefix+'/sprite',inventory_sheet=prefix+'/inventory',index=0,columns=1)
                for name,size in [('sprite_16.png',(16,16)),('inventory_48.png',(48,72))]:
                    store.pending_assets[f'assets/{prefix}/{name}']=encode(Image.new('RGBA',size,(n,30,60,100+n)))
            store.data['sprites']['alias']=dict(store.data['sprites']['0'])
            before=copy.deepcopy(store.data)
            with patch.object(atlas,'SIZES',(16,)),patch.object(atlas,'WIDTHS',(48,)):
                current,previous,files=atlas.pack(store)
            self.assertEqual(store.data,before)
            self.assertEqual(current['alias'],current['0'])
            self.assertEqual(len({e['sheet'] for e in current.values()}),2)
            self.assertEqual(len(files),4)
            for n in range(65):
                e=current[str(n)]
                for field,size,h in [('sheet',16,16),('inventory_sheet',48,72)]:
                    with Image.open(io.BytesIO(files[f"assets/{e[field]}_{size}.png"])) as image:
                        columns=e['columns'];x=e['index']%columns*size;y=e['index']//columns*h
                        self.assertEqual(image.getpixel((x,y)),(n,30,60,100+n))
                        self.assertLessEqual(image.width,8*size);self.assertLessEqual(image.height,8*h)

    def test_cleanup_protects_backups_originals_and_unknown_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);custom=root/'assets/custom';custom.mkdir(parents=True);(root/'data').mkdir()
            for name in ('old','kept'):
                d=custom/name;d.mkdir();(d/'sprite_16.png').write_bytes(b'image')
            (custom/'original.png').write_bytes(b'original')
            (root/'data/sprites.json.bak').write_text(json.dumps({'art':{'sheet':'custom/kept/sprite'}}))
            self.assertEqual(atlas.cleanup(root),1)
            self.assertTrue((custom/'kept/sprite_16.png').exists())
            self.assertTrue((custom/'original.png').exists())
            self.assertFalse((custom/'old').exists())
