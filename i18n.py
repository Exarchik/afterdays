"""UTF-8 translation catalogs; missing translations fall back to Ukrainian."""
import json,os
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def catalog(language):
    if not language.replace('-','').replace('_','').isalnum():raise ValueError('Invalid language code')
    result={}
    for path in sorted((ROOT/'locales'/language).glob('*.json')):
        values=json.loads(path.read_text(encoding='utf-8'))
        for key,value in values.items():
            if key in result:raise ValueError(f'Duplicate translation key: {key}')
            if not isinstance(value,str):raise ValueError(f'Translation must be a string: {key}')
            result[key]=value
    return result

settings=ROOT/'settings.json'
LANGUAGE=os.environ.get('AFTERDAYS_LANGUAGE') or (json.loads(settings.read_text(encoding='utf-8')).get('language','uk') if settings.exists() else 'uk')
FALLBACK=catalog('uk');TRANSLATIONS=catalog(LANGUAGE) if LANGUAGE!='uk' else dict(FALLBACK)

def t(key,**values):
    template=TRANSLATIONS.get(key,FALLBACK.get(key,key))
    if not values:return template
    try:return template.format(**values)
    except (KeyError,ValueError,IndexError):return FALLBACK.get(key,key).format(**values)
