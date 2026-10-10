"""Single, validated source of road events. No game or GUI imports."""
import copy
import json
import math
import os
from pathlib import Path
import re
import tempfile

ROOT = Path(__file__).resolve().parent
PATH = ROOT / 'data' / 'road_events.json'
CATEGORIES = {
    'help': 'Допомога й зустрічі', 'trade': 'Обмін і торгівля',
    'exploration': 'Дослідження й мапа', 'supplies': 'Припаси й лікування',
    'salvage': 'Матеріали й знахідки', 'repair': 'Ремонт спорядження',
    'hazards': 'Небезпеки й втрати', 'caches': 'Замкнені сховки',
}
TERRAINS = {'any': 'Будь-де', 'road': 'Дорога', 'forest': 'Ліс', 'ruin': 'Руїни', 'waste': 'Пустка'}
EFFECTS = {
    'fence_hole': ('Прохід у паркані', 'Відкрити постійний прохід поруч із гравцем після дозволу мера.'),
    'money': ('Кредити', 'Додати кредити; від’ємне число — втрата, до нуля.'),
    'xp': ('Досвід', 'Кінцева кількість XP; чинний штраф боягузтва зменшує її вдвічі.'),
    'heal': ('Лікування', 'Відновити HP до максимального здоров’я.'),
    'damage': ('Шкода', 'Зняти HP. Може спричинити поразку.'),
    'food': ('Їжа', 'Додати їжу до здобичі; від’ємне число забирає наявну з рюкзака.'),
    'med': ('Аптечки', 'Додати аптечки; від’ємне число забирає наявні.'),
    'rad': ('Радіопротектори', 'Додати предмети радіопротекції; це не миттєвий захист.'),
    'repairkit': ('Ремкомплекти', 'Додати ремкомплекти; від’ємне число забирає наявні.'),
    'parts': ('Запчастини', 'Додати запчастини; від’ємне число забирає наявні.'),
    'fragments': ('Фрагменти', 'Додати фрагменти; від’ємне число забирає наявні.'),
    'ammo': ('Набої', 'Вибрати тип набоїв або випадковий тип.'),
    'reveal': ('Відкриття мапи', 'Кількість — радіус відкриття навколо гравця.'),
    'repair_weapon': ('Ремонт зброї', 'Додати пункти стану активній зброї; потрібна екіпірована зброя.'),
    'repair_armor': ('Ремонт броні', 'Додати пункти стану броні; потрібна екіпірована броня.'),
    'wear_armor': ('Пошкодження броні', 'Зносити екіпіровану броню на задану кількість пунктів стану з урахуванням міцності.'),
    'radiation': ('Доза радіації', 'Додати відсоткові пункти радіаційного пошкодження; 100% спричиняє загибель.'),
    'radiation_heal': ('Лікування від радіації', 'Прибрати відсоткові пункти радіаційного пошкодження. Звичайні рани не лікує.'),
    'satiety_gain': ('Збільшити насичення (шкалу голоду)', 'Додати поділки шкали голоду, максимум 20. Втамовує голод, не додає предметів їжі.'),
    'satiety_loss': ('Зменшити насичення (шкалу голоду)', 'Забрати поділки шкали голоду, мінімум −20. Посилює голод; −20 спричиняє загибель. Обжертість блокує зменшення.'),
    'buff_regen': ('Регенерація', 'Кількість — бонус HP після бою та поступово за 30 кроків; тривалість — кроки мапою. Повторне застосування замінює силу й час.'),
    'buff_satiety': ('Обжертість', 'Утримує насичення на 20 протягом заданої кількості кроків мапою. Їжа не витрачається; кількість ігнорується.'),
    'buff_stealth': ('Непомітність', 'Протягом заданих кроків мапою шанс випадкового нападу втричі менший. Квестові бої не змінюються; кількість ігнорується.'),
    'wear': ('Знос зброї', 'Зносити активну зброю на задану кількість пунктів.'),
    'discover': ('Відкрити локацію', 'Відкрити найближчу невідому локацію; кількість — XP, якщо всі вже відкриті.'),
    'gear': ('Спорядження', 'Випадковий предмет рівня місцевості (від L−2 до L), стан 30–90.'),
    'cache': ('Відкрити замок', 'Створити постійний сховок із вмістом на вкладці «Сховок» і відкрити мінігру.'),
}
TIMED_EFFECTS = {'buff_regen','buff_satiety','buff_stealth'}
ITEM_KINDS = {'food', 'med', 'rad', 'repairkit', 'parts', 'fragments', 'ammo'}
CACHE_KINDS = ITEM_KINDS | {'gear', 'money'}
AMMO = ('random', 'pistol', 'rifle', 'shell', 'energy', 'heavy', 'bolt')
COSTS = ('money', 'food', 'med', 'rad', 'repairkit', 'parts', 'fragments')

def art_catalog():
    result = json.loads((ROOT / 'assets/manifest.json').read_text(encoding='utf-8'))
    result.update(json.loads((ROOT / 'data/sprites.json').read_text(encoding='utf-8')))
    return result

def ordered(events):
    order = list(CATEGORIES)
    return sorted(events, key=lambda e: (order.index(e['category']), e['terrain'], e['title'].casefold(), e['id']))

def consumable_catalog():
    return json.loads((ROOT/'data/consumables.json').read_text(encoding='utf-8'))

def validate(document, art=None, consumables=None):
    """Reject malformed content before writing or applying any game effects."""
    errors = []
    def need(ok, label):
        if not ok: errors.append(label)
    def number(v): return type(v) in (int, float) and math.isfinite(v)
    def integer(v): return type(v) is int
    if not isinstance(document, dict) or document.get('version') != 1 or not isinstance(document.get('events'), list):
        return ['Потрібен каталог version=1 зі списком events.']
    if art is None:art = art_catalog()
    if consumables is None:consumables=consumable_catalog()
    ids = set()
    for event in document['events']:
        if not isinstance(event, dict): errors.append('Подія має бути об’єктом.'); continue
        ident = event.get('id', '')
        label = str(ident) + ': '
        need(isinstance(ident, str) and bool(re.fullmatch('[a-z][a-z0-9_]*', ident)), label+'некоректний ID')
        token = str(ident)
        need(token not in ids, label+'повторний ID'); ids.add(token)
        need(event.get('category') in CATEGORIES, label+'невідома категорія')
        need(event.get('terrain') in TERRAINS, label+'невідома місцевість')
        need(type(event.get('enabled')) is bool, label+'enabled має бути bool')
        need(number(event.get('weight')) and event['weight'] > 0, label+'вага має бути > 0')
        for field in ('title', 'description'):
            need(isinstance(event.get(field), str) and bool(event[field].strip()), label+field+' порожнє')
        need(event.get('art') in art, label+'невідоме зображення')
        def effects(rows, in_cache=False):
            if not isinstance(rows, list): errors.append(label+'ефекти мають бути списком'); return
            for effect in rows:
                if not isinstance(effect, dict): errors.append(label+'ефект має бути об’єктом'); continue
                kind = effect.get('kind')
                need(kind in EFFECTS, label+'невідомий ефект '+str(kind))
                if 'item_id' in effect:
                    item_id=effect['item_id']
                    need(kind in ('food','med','rad','repairkit') and isinstance(item_id,str) and (item_id=='random' or consumables.get(item_id,{}).get('kind')==kind),label+'предмет не відповідає категорії нагороди')
                need(not in_cache or kind in CACHE_KINDS, label+'у сховку дозволені лише предмети та кредити')
                for field, default in (('amount', 1), ('per_level', 0), ('step', 0), ('step_cap', 0)):
                    need(integer(effect.get(field, default)), label+field+' має бути цілим')
                for field in ('step', 'step_cap'):
                    need(integer(effect.get(field, 0)) and effect.get(field, 0) >= 0, label+field+' має бути ≥ 0')
                if 'maximum' in effect:
                    need(integer(effect['maximum']) and integer(effect.get('amount', 1)) and effect['maximum'] >= effect.get('amount', 1), label+'неправильний діапазон кількості')
                chance = effect.get('chance', 1)
                need(number(chance) and 0 <= chance <= 1, label+'шанс ефекту має бути 0–1')
                need(effect.get('destination', 'loot') in ('loot', 'bag'), label+'невідоме місце нагороди')
                if kind in TIMED_EFFECTS:
                    need(integer(effect.get('duration')) and 1 <= effect['duration'] <= 1000000, label+'тривалість бафа: 1–1000000 кроків')
                if kind == 'ammo': need(effect.get('ammo', 'random') in AMMO, label+'невідомий тип набоїв')
                if kind not in ITEM_KINDS | {'money'}:
                    need(integer(effect.get('amount', 1)) and effect.get('amount', 1) >= 0 and integer(effect.get('per_level', 0)) and effect.get('per_level', 0) >= 0, label+'для цього ефекту кількість має бути ≥ 0')
                if in_cache:
                    need(integer(effect.get('amount', 1)) and effect.get('amount', 1) > 0 and integer(effect.get('per_level', 0)) and effect.get('per_level', 0) >= 0, label+'предмети сховку мають мати додатну кількість')
                if kind == 'cache': need(bool(event.get('cache')), label+'відсутній вміст сховку')
        choices = event.get('choices')
        if not isinstance(choices, list) or not choices: errors.append(label+'потрібна хоча б одна дія'); continue
        choice_ids = set()
        for choice in choices:
            if not isinstance(choice, dict): errors.append(label+'дія має бути об’єктом'); continue
            cid = choice.get('id', '')
            need(isinstance(cid, str) and bool(re.fullmatch('[a-z][a-z0-9_]*', cid)), label+'некоректний ID дії')
            need(str(cid) not in choice_ids, label+'повторний ID дії'); choice_ids.add(str(cid))
            need(isinstance(choice.get('text'), str) and bool(choice['text'].strip()), label+'порожній текст дії')
            costs = choice.get('costs', [])
            if not isinstance(costs, list): errors.append(label+'витрати мають бути списком'); costs=[]
            for cost in costs:
                need(isinstance(cost, dict) and cost.get('kind') in COSTS and integer(cost.get('amount')) and cost['amount'] > 0, label+'некоректна витрата')
            outcomes = choice.get('outcomes')
            if not isinstance(outcomes, list) or not outcomes: errors.append(label+'потрібен хоча б один результат'); continue
            total = 0
            for outcome in outcomes:
                if not isinstance(outcome, dict): errors.append(label+'результат має бути об’єктом'); continue
                chance = outcome.get('chance')
                need(number(chance) and 0 <= chance <= 1, label+'шанс результату має бути 0–1')
                if number(chance): total += chance
                effects(outcome.get('effects', []))
            need(abs(total - 1) < 1e-8, label+'сума шансів результатів має бути 100%')
        if 'cache' in event: effects(event['cache'], True)
    return errors

def load(path=PATH, art=None):
    document = json.loads(Path(path).read_text(encoding='utf-8'))
    errors = validate(document,art=art)
    if errors: raise ValueError('\n'.join(errors))
    return document

def save(document, path=PATH):
    """Validate, back up and replace atomically; never partially overwrite the catalog."""
    errors = validate(document)
    if errors: raise ValueError('\n'.join(errors))
    path = Path(path)
    doc = copy.deepcopy(document); doc['events'] = ordered(doc['events'])
    text = json.dumps(doc, ensure_ascii=False, indent=2) + '\n'
    if path.exists(): path.with_suffix(path.suffix+'.bak').write_bytes(path.read_bytes())
    fd, temporary = tempfile.mkstemp(prefix=path.name+'.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream: stream.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)

def amount(effect, level, rng):
    n = effect.get('amount', 1)
    if 'maximum' in effect: n = rng.randint(n, effect['maximum'])
    n += effect.get('per_level', 0) * level
    if effect.get('step', 0): n += min(effect.get('step_cap', 0), max(0, level-1)//effect['step'])
    return n

def describe(effect):
    kind = effect['kind']; n = str(effect.get('amount', 1))
    if 'maximum' in effect: n += '…'+str(effect['maximum'])
    if effect.get('per_level'): n += f" + {effect['per_level']}×L"
    if effect.get('step'): n += f" + min({effect.get('step_cap', 0)}, ⌊(L−1)/{effect['step']}⌋)"
    if kind in ('cache', 'gear'): n = ''
    suffix = ' ['+effect.get('ammo', 'random')+']' if kind == 'ammo' else ''
    if effect.get('item_id'):
        ident=effect['item_id'];suffix+=' ['+('Випадковий' if ident=='random' else consumable_catalog().get(ident,{}).get('name',ident))+']'
    if kind in TIMED_EFFECTS:
        n = (n+' HP; ' if kind=='buff_regen' else '') + str(effect.get('duration','?'))+' кроків'
    if kind in ('radiation','radiation_heal'): n+=' в.п.'
    chance = f" ({effect['chance']*100:g}%)" if effect.get('chance', 1) != 1 else ''
    if kind == 'xp': return f'{n} XP{chance}'
    return f'{EFFECTS[kind][0]}{suffix}: {n}{chance}'.rstrip(': ')

def choice_text(choice):
    pieces = []
    if choice.get('costs'):
        pieces.append('Витрата: '+', '.join(describe(c) for c in choice['costs']))
    for result in choice['outcomes']:
        if not result.get('effects'): continue
        prefix = f"{result['chance']*100:g}%: " if result['chance'] != 1 else ''
        pieces.append(prefix+', '.join(describe(e) for e in result['effects']))
    return choice['text'] + (' — '+'; '.join(pieces) if pieces else '')

DOCUMENT = load()
EVENTS = DOCUMENT['events']
BY_ID = {e['id']: e for e in EVENTS}
