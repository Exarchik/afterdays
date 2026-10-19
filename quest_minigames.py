"""Editable minigame settings of native quest types, shared by profiles and the editor."""
import importlib

# kind -> editor block: title, settings module, field labels, optional art field and a note.
MINIGAMES={
    'radiation_source':dict(
        title='Мінігра «Дозиметр»',module='game.systems.radiation_source',
        fields=[('grid_size','Розмір ділянки, гексів по стороні'),
                ('max_dose','Радіація за замір біля джерела'),
                ('device_radiation','Радіація від приладу за крок')],
        art=('device_art','Арт приладу (порожньо — стандартна іконка)'),
        note='Заміри без обмежень: гравець шукає, доки не заміряє сам гекс із джерелом. Єдина ціна довгого пошуку — накопичена радіація.\n'
             'Після знахідки гравець несе радіоактивний прилад замовнику; радіопротектор блокує опромінення від нього.'),
    'electronics_repair':dict(
        title='Мінігра «Монтаж мікросхем»',module='game.systems.electronics',
        fields=[('contacts_min','Контактів на модулі, від'),
                ('contacts_max','Контактів на модулі, до'),
                ('decoys','Зайвих модулів у лотку'),
                ('hints','Підсвічувати клеми при перетягуванні'),
                ('shock','Удар струмом при помилці, HP')],
        art=None,
        note='Гнізда показують лише клеми; модуль підходить, коли всі його контакти лягли на клеми, а контакт 1 — на квадратну.\n'
             'Розкладка контактів генерується від ID квесту на краю арту модуля. Провалу немає: помилкові гнізда іскрять.'),
    'junkyard':dict(
        title='Мінігра «Розбір завалу»',module='junk_physics',
        fields=[('parts','Квестових деталей у завалі'),
                ('max_stamina','Запас сил'),
                ('stamina_per_satiety','Сил за 1 очко ситості з їжі')],
        art=None,
        note='Уламок можна прибрати, лише коли на ньому нічого не лежить. Вартість: газети й картон 1, дошка 2, мішок 3, лист металу 5, бетонна плита 8.\n'
             'Сили відновлює лише їжа, з’їдена на звалищі; запас не перевищує максимум.'),
    'elite_hunt':dict(
        title='Мінігра «Сканер слідів»',module='game.systems.track_scanner',
        fields=[('needed','Відбитків прочитати (з 6)'),
                ('drain','Розряд увімкненого сканера, % за 10 с'),
                ('recharge','Відновлення вимкненого сканера, % за 10 с'),
                ('lens_speed','Швидкість увімкненого сканера, пікс/с')],
        art=None,
        note='На першій точці «Пошук» відкриває сканер: на ділянці одна група відбитків у випадковому місці.\n'
             'Вимкнений сканер рухається вільно й підзаряджається, увімкнений — важкий і розряджається. '
             'Прочитані відбитки вказують напрям, і лігво позначається на мапі за 3–6 гексів у цьому напрямку.'),
}


def module(kind):
    return importlib.import_module(MINIGAMES[kind]['module'])


def defaults(kind):
    """Default minigame fields for a native quest profile; empty for other types."""
    if kind not in MINIGAMES:return {}
    values=module(kind).settings_for({})
    art=MINIGAMES[kind]['art']
    if art:values[art[0]]=''
    return values


def validate(kind,spec,prefix=''):
    if kind not in MINIGAMES:return []
    return module(kind).validate_settings(spec,prefix)


def limits(kind,key):
    return module(kind).SETTINGS[key]
