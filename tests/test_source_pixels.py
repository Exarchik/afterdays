import io,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from PIL import Image,PngImagePlugin
from art_library import Library,DEFAULTS
from tools.deduplicate_art_sources import compact


class SourcePixelsTests(unittest.TestCase):
    def test_different_encoding_shared_reference_and_reimport(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);sources=root/'assets/custom/sources';sources.mkdir(parents=True);(root/'data').mkdir()
            image=Image.new('RGBA',(32,32),(10,20,30,125));info=PngImagePlugin.PngInfo();info.add_text('Comment','duplicate')
            image.save(sources/'first.png',compress_level=0)
            image.save(sources/'second.png',pnginfo=info,compress_level=9)
            Image.new('RGBA',(32,32),(10,20,30,126)).save(sources/'different.png')
            doc={'a':{'editor_source':'custom/sources/first.png'},'b':{'editor_source':'custom/sources/second.png'}}
            for name in ('sprites.json','sprites.json.bak'):(root/'data'/name).write_text(json.dumps(doc))
            self.assertEqual(compact(root,pixels=True)['duplicate_sources'],1)
            self.assertEqual(len(list(sources.glob('*.png'))),3)
            compact(root,True,True)
            self.assertEqual(len(list(sources.glob('*.png'))),2)
            loaded=json.loads((root/'data/sprites.json').read_text())
            self.assertEqual(loaded['a']['editor_source'],loaded['b']['editor_source'])
            self.assertEqual(loaded,json.loads((root/'data/sprites.json.bak').read_text()))
            self.assertEqual(compact(root,pixels=True)['duplicate_sources'],0)
            store=SimpleNamespace(root=root,pending_assets={},art={},data={'sprites':{},'equipment':{},'modules':{},'monsters':{},'consumables':{}})
            store.refresh_art=lambda:store.art.update(store.data['sprites'])
            Library(store).stage('art_test','Test','other',image,DEFAULTS)
            self.assertFalse(any('/sources/' in p for p in store.pending_assets))
            self.assertEqual(store.data['sprites']['art_test']['editor_source'],loaded['a']['editor_source'])
