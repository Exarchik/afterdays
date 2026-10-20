"""How an enemy's attack looks on the arena: its weapon's projectile or the monster's own.

Armed people fire the projectile of their weapon's damage type. Monsters get a style by
model ID; monsters added in the editor are matched by words in the ID or name, and fall
back to claws (melee) or spit (ranged).
"""
import content

MONSTERS={'monster_rodent':'bite','monster_feral':'claw','monster_spitter':'spit','monster_blind_hound':'bite',
          'monster_shellback':'smash','monster_acid_tick':'acid','monster_ash_wolf':'claw','monster_sentry_drone':'laser',
          'monster_swamp_mutant':'mud','monster_bone_giant':'smash','monster_spark':'spark','monster_chimera_spider':'web'}
KEYWORDS=(('acid','acid'),('кисл','acid'),('spit','spit'),('плюв','spit'),('drone','laser'),('дрон','laser'),
          ('turret','laser'),('турел','laser'),('spark','spark'),('іскр','spark'),('electr','spark'),('спайдер','web'),
          ('spider','web'),('павук','web'),('swamp','mud'),('болот','mud'),('wolf','claw'),('вовк','claw'),
          ('hound','bite'),('гонч','bite'),('пес','bite'),('dog','bite'),('rodent','bite'),('гриз','bite'),('щур','bite'),
          ('rat','bite'),('giant','smash'),('велет','smash'),('shell','smash'),('панцир','smash'),('голем','smash'))
MELEE={'bite','claw','smash','punch'}


def style_of(actor):
    try:ident=str(content.monster_id(actor))
    except (KeyError,IndexError,TypeError,ValueError):ident=''
    if ident in MONSTERS:return MONSTERS[ident]
    text=(ident+' '+str(actor.get('name',''))).lower()
    for word,style in KEYWORDS:
        if word in text:return style
    return 'claw' if actor.get('range',1)<=1 else 'spit'


def look(actor):
    """Event fields for the attack animation of an enemy or an armed person."""
    from game.systems.adventure import damage_type
    weapon=(actor.get('equipment') or {}).get('weapon')
    if weapon and actor.get('range',1)>1:return dict(damage_type=damage_type(weapon))
    if actor.get('human'):return dict(attack_style='punch')
    style=style_of(actor)
    return dict(damage_type='electric') if style=='spark' else dict(attack_style=style)
