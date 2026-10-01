"""Authored contracts reuse native quest mechanics and persist accepted snapshots."""
import copy,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent
TYPES={
'hunt':('Полювання','Убити задану кількість монстрів поблизу міста.'),
'retrieve':('Пошук предмета','Знайти квестовий предмет і повернути його.'),
'scout':('Розвідка','Дослідити ділянку мапи.'),
'supplies':('Постачання','Принести їжу й аптечки.'),
'purge':('Зачистка','Очистити бойову локацію.'),
'trophies':('Трофеї','Зібрати трофеї визначеного виду монстра.'),
'delivery':('Доставка','Доставити посилку доступному одержувачу.'),
'repair_delivery':('Ремонт і доставка','Полагодити виданий предмет і доставити його.'),
'radio':('Радіосигнал','Налаштувати радіо у визначеній точці.'),
'field_test':('Випробування спорядження','Виконати випробування виданого спорядження.'),
'generator':('Генератор','Відремонтувати генератор за допомогою матеріалів і головоломки.'),
'cache':('Схованка','Знайти схованку в позначеній області.'),
'elite_hunt':('Елітне полювання','Вистежити й перемогти елітного монстра.'),
'torn_map':('Розірвана мапа','Зібрати частини мапи та знайти скарб.'),
'junkyard':('Звалище','Обшукати звалище з мінігрою.')}
SPECIAL={
'recruit_smith':('Поселення коваля','Видається під час зустрічі з кандидатом; прив’язане до поселення.'),
'recruit_tech':('Поселення техніка','Видається під час зустрічі з кандидатом; прив’язане до поселення.'),
'recruit_mayor':('Поселення мера','Видається під час зустрічі з кандидатом; прив’язане до поселення.'),
'permit':('Дозвіл на перехід','Сюжетний квест кордону.'),
'thanks':('Подяка міста','Автоматична подяка за репутацію.'),
'metro':('Відновлення метро','Ланцюжок етапів, прив’язаний до станції метро.')}


def draft(ident):
    return dict(id=ident,title='Новий квест',description='',kind='hunt',enabled=True,repeatable=False,cooldown=100,
                min_level=1,max_level=100,min_reputation=0,max_reputation=100,min_turn=0,cities=[],requires=[],
                goal=4,food_need=3,med_need=2,reward=150,xp_reward=40)


def validate(doc):
    errors=[]
    if not isinstance(doc,dict) or doc.get('version')!=1 or not isinstance(doc.get('quests'),list):return ['Некоректний каталог квестів.']
    ids=[q.get('id') for q in doc['quests'] if isinstance(q,dict)]
    for q in doc['quests']:
        if not isinstance(q,dict):errors.append('Квест має бути об’єктом.');continue
        ident=q.get('id');prefix=str(ident)+': '
        def need(ok,msg):
            if not ok:errors.append(prefix+msg)
        need(isinstance(ident,str) and bool(re.fullmatch('[a-z][a-z0-9_]*',ident)),'ID: латинські літери, цифри, підкреслення.')
        need(ids.count(ident)==1,'ID повторюється.')
        need(q.get('kind') in TYPES,'Невідомий тип авторського квесту.')
        need(isinstance(q.get('title'),str) and bool(q['title'].strip()),'Назва порожня.')
        need(isinstance(q.get('description'),str),'Опис має бути текстом.')
        for name in ('enabled','repeatable'):need(type(q.get(name)) is bool,'Некоректний перемикач '+name)
        for name,low,high in [('min_level',1,100),('max_level',1,100),('min_reputation',0,100),('max_reputation',0,100),
                              ('min_turn',0,1000000),('cooldown',1,1000000),('goal',1,10000),('food_need',0,10000),('med_need',0,10000),('reward',0,10000000),('xp_reward',0,10000000)]:
            need(type(q.get(name)) is int and low<=q[name]<=high,'Некоректне значення '+name)
        for low,high in [('min_level','max_level'),('min_reputation','max_reputation')]:
            if type(q.get(low)) is int and type(q.get(high)) is int:need(q[low]<=q[high],'Мінімум більший за максимум.')
        need(isinstance(q.get('cities'),list) and all(type(n) is int and n>=0 for n in q['cities']),'Міста: невід’ємні числові ID.')
        need(isinstance(q.get('requires'),list) and all(isinstance(n,str) and n in ids and n!=ident for n in q['requires']),'Попередники: ID інших авторських квестів.')
    if errors:return errors
    graph={q['id']:q['requires'] for q in doc['quests']}
    done=set();visiting=set()
    def visit(ident):
        if ident in visiting:return False
        if ident in done:return True
        visiting.add(ident)
        if not all(visit(n) for n in graph[ident]):return False
        visiting.remove(ident);done.add(ident);return True
    if not all(visit(n) for n in graph):errors.append('Циклічна залежність між квестами.')
    return errors


def load(path=None):
    path=Path(path or ROOT/'data/quests.json')
    doc=json.loads(path.read_text(encoding='utf-8')) if path.exists() else dict(version=1,quests=[])
    errors=validate(doc)
    if errors:raise ValueError('\n'.join(errors))
    return doc


def eligible(game,spec):
    if not spec['enabled'] or game.city is None:return False
    if not spec['min_level']<=game.level<=spec['max_level']:return False
    if not spec['min_reputation']<=game.reputation(game.city)<=spec['max_reputation']:return False
    if game.turn<spec['min_turn'] or (spec['cities'] and game.city not in spec['cities']):return False
    completed={q.get('authored_id') for q in game.quests if q['status']=='done'}
    if not set(spec['requires'])<=completed:return False
    history=game.reputation_state.get('authored_history',{}).get(spec['id'])
    if any(q.get('authored_id')==spec['id'] and q['status']=='active' for q in game.quests):return False
    if spec['id'] in completed and not spec['repeatable']:return False
    if history is not None and (not spec['repeatable'] or game.turn-history<spec['cooldown']):return False
    return True


DOCUMENT=load()
