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
    'junkyard':dict(
        title='Мінігра «Розбір завалу»',module='junk_physics',
        fields=[('parts','Квестових деталей у завалі'),
                ('max_stamina','Запас сил'),
                ('stamina_per_satiety','Сил за 1 очко ситості з їжі')],
        art=None,
        note='Уламок можна прибрати, лише коли на ньому нічого не лежить. Вартість: газети й картон 1, дошка 2, мішок 3, лист металу 5, бетонна плита 8.\n'
             'Сили відновлює лише їжа, з’їдена на звалищі; запас не перевищує максимум.'),
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
