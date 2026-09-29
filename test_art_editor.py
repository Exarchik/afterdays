"""Import, replace and persist artwork without changing shared source atlases."""
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
import art_library as art
from entity_catalog import Store
import event_catalog
from test_entity_editor import project_copy


def fixture():
    image=Image.new('RGBA',(320,200))
    image.paste((255,20,30,255),(60,30,150,180));image.paste((20,220,100,170),(150,30,270,180))
    return image


class ArtTests(unittest.TestCase):
    def test_identical_arts_and_metadata_reuse_files_but_crop_shares_only_source(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(project_copy(folder));library=art.Library(store)
            library.stage('art_test_a','A','events',fixture(),art.DEFAULTS)
            library.stage('art_test_b','B','monsters',fixture(),art.DEFAULTS)
            self.assertEqual(len(store.pending_assets),15)
            self.assertEqual(library.entries['art_test_a']['sheet'],library.entries['art_test_b']['sheet'])
            store.save()
            library.stage('art_test_a','Renamed','other',fixture(),art.DEFAULTS)
            self.assertFalse(store.pending_assets)
            library.stage('art_test_c','Crop','events',fixture(),dict(art.DEFAULTS,crop=[60,30,150,180]))
            self.assertEqual(len(store.pending_assets),14)
            self.assertEqual(library.entries['art_test_a']['editor_source'],library.entries['art_test_c']['editor_source'])
            store.save()
            self.assertEqual(len(list((Path(folder)/'assets/custom/sources').glob('*.png'))),1)

    def test_source_compaction_preserves_backups_unique_files_and_legacy_reuse(self):
        from tools.deduplicate_art_sources import compact
        with tempfile.TemporaryDirectory() as folder:
            root=project_copy(folder);store=Store(root);library=art.Library(store)
            library.stage('art_test','Test','events',fixture(),art.DEFAULTS);store.save()
            original=library.entries['art_test']['editor_source']
            legacy=root/'assets/custom/legacy/source.png';legacy.parent.mkdir(parents=True)
            legacy.write_bytes((root/'assets'/original).read_bytes())
            catalog=root/'data/old.json.bak'
            catalog.write_text(json.dumps({'editor_source':'custom/legacy/source.png'}),encoding='utf-8')
            unique=root/'assets/custom/unique/source.png';unique.parent.mkdir()
            unique.write_bytes(art.encode(Image.new('RGBA',(12,12),'blue')))
            before={p:p.read_bytes() for p in (root/'assets/custom').rglob('*.png')}
            report=compact(root);self.assertEqual(report['duplicate_sources'],1)
            self.assertEqual(before,{p:p.read_bytes() for p in before})
            catalogs={p:p.read_bytes() for p in (root/'data').glob('*.json*')}
            with patch('tools.deduplicate_art_sources.os.replace',side_effect=OSError('write failure')):
                with self.assertRaises(OSError):compact(root,True)
            self.assertEqual(catalogs,{p:p.read_bytes() for p in catalogs})
            self.assertEqual(before,{p:p.read_bytes() for p in before})
            compact(root,True)
            for p in (root/'data/sprites.json',catalog):
                data=json.loads(p.read_text(encoding='utf-8'))
                entry=data if p==catalog else data['art_test']
                self.assertEqual((root/'assets'/entry['editor_source']).read_bytes(),art.encode(fixture()))
            self.assertFalse(unique.exists())
            self.assertIn(art.encode(Image.new('RGBA',(12,12),'blue')),
                          [p.read_bytes() for p in (root/'assets/custom/sources').glob('*.png')])
            self.assertEqual(compact(root)['sources_relocated'],0)
            loaded=Store(root);lib=art.Library(loaded)
            lib.stage('art_test','Edited','events',fixture(),art.DEFAULTS)
            self.assertFalse(loaded.pending_assets)

    def test_crop_rotation_alpha_and_inventory_sizes(self):
        image=fixture();settings=dict(art.DEFAULTS,crop=[60,30,270,180],rotation=90,mirror=True,padding=0)
        result=art.transformed(image,settings);self.assertEqual(result.size,(150,210))
        for size in art.SIZES:
            tile=art.tile(image,settings,size);self.assertEqual(tile.size,(size,size));self.assertEqual(tile.mode,'RGBA')
            self.assertEqual(tile.getpixel((0,0))[3],0)
        for width in art.WIDTHS:self.assertEqual(art.inventory(image,settings,width).size,(width,72))
        cover=art.tile(Image.new('RGBA',(300,100),'red'),dict(art.DEFAULTS,fit='cover',padding=0),192)
        self.assertEqual(cover.getpixel((0,0)),(255,0,0,255))

    def test_invalid_crop_and_empty_image_rejected(self):
        for crop in ([0,0,999,1],[2,2,1,1],[-1,0,20,20]):
            with self.assertRaises(ValueError):art.tile(fixture(),dict(art.DEFAULTS,crop=crop),192)
        with self.assertRaises(ValueError):art.tile(Image.new('RGBA',(10,10)),art.DEFAULTS,192)

    def test_import_stage_save_reload_all_sizes_and_event_reference(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(project_copy(folder));library=art.Library(store);key=library.next_id()
            library.stage(key,'Новий арт','events',fixture(),art.DEFAULTS)
            self.assertTrue(store.dirty);self.assertEqual(len(store.pending_assets),15)
            self.assertFalse((Path(folder)/'assets/custom').exists())
            events=event_catalog.load();events['events'][0]['art']=key
            self.assertFalse(event_catalog.validate(events,art=store.art))
            ep=Path(folder)/'data/road_events.json';store.save((ep,events,ep.read_bytes()))
            loaded=Store(folder);other=art.Library(loaded);entry=other.entries[key]
            self.assertFalse(loaded.dirty);self.assertEqual(other.source(key).tobytes(),fixture().tobytes())
            for size in art.SIZES:
                with Image.open(Path(folder)/'assets'/f"{entry['sheet']}_{size}.png") as img:self.assertEqual(img.size,(size,size))
            for width in art.WIDTHS:
                with Image.open(Path(folder)/'assets'/f"{entry['inventory_sheet']}_{width}.png") as img:self.assertEqual(img.size,(width,72))
            self.assertEqual(event_catalog.load(ep,art=loaded.art)['events'][0]['art'],key)

    def test_replacement_keeps_id_and_updates_model_aliases(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(project_copy(folder));library=art.Library(store)
            key='monster_rodent';copy_id=store.add('monster','Другий гризун',key)
            original=copy.deepcopy(store.base_art)
            library.stage(key,'Оновлений гризун','monsters',fixture(),art.DEFAULTS)
            self.assertEqual(store.data['sprites'][copy_id]['sheet'],store.data['sprites'][key]['sheet'])
            self.assertEqual(store.base_art,original)
            first=store.data['sprites'][key]['sheet'];store.save()
            library.stage(key,'Інша назва','monsters',fixture(),dict(art.DEFAULTS,rotation=90))
            self.assertNotEqual(store.data['sprites'][key]['sheet'],first);store.save()
            self.assertTrue((Path(folder)/'assets'/f'{first}_192.png').exists())
            self.assertEqual(json.loads((Path(folder)/'data/sprites.json.bak').read_text(encoding='utf-8'))[key]['sheet'],first)

    def test_failed_import_and_failed_save_do_not_leave_broken_catalogs(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(project_copy(folder));library=art.Library(store);before=copy.deepcopy(store.data)
            with self.assertRaises(ValueError):library.stage('art_custom_001','Bad','events',fixture(),dict(art.DEFAULTS,padding=99))
            self.assertEqual(store.data,before);self.assertFalse(store.pending_assets)
            library.stage('art_custom_001','Good','events',fixture(),art.DEFAULTS)
            snapshot={key:path.read_bytes() for key,path in store.paths.items()};replace=os.replace
            def fail_catalog(source,target):
                if Path(target)==store.paths['sprites']:raise OSError('simulated write failure')
                return replace(source,target)
            with patch('entity_catalog.os.replace',side_effect=fail_catalog):
                with self.assertRaises(OSError):store.save()
            self.assertEqual(snapshot,{key:path.read_bytes() for key,path in store.paths.items()})
            self.assertFalse(list((Path(folder)/'assets/custom').rglob('*.png')))
            self.assertTrue(store.dirty);store.save();self.assertFalse(store.dirty)

    def test_generated_paths_cannot_escape_assets(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(project_copy(folder));store.pending_assets['../escape.png']=b'bad'
            with self.assertRaises(ValueError):store.save()


if __name__=='__main__':unittest.main()
