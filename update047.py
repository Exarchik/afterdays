"""Faction-aware encounters and safe arena exits for v0.47."""
import copy
import balance
import content
import hexgrid
import progression as p
import update046
import faction_rules as rules
from recovery047 import Recovery


class Game(Recovery,update046.Game):
    def start_battle(self):
        super().start_battle()
        b=self.battle
        if not b:return
        if self.quest_battle or b.get('dungeon'):
            self.prepare_factions();return
        import monster_rules
        doc=rules.catalog();level=b.get('region_level',self.region_level)
        factions,pools=rules.encounter_factions(self.rng,doc,content.MONSTER_DATA,level,len(b['enemies']))
        b['entrance047']=b['pos'][:]
        for n,(old,faction) in enumerate(zip(b['enemies'],factions)):
            members=pools[faction]
            weights=[1 if k in doc['humans'] else monster_rules.spawn_weight(k,level) for k in members]
            ident=self.rng.choices(members,weights=weights,k=1)[0]
            if ident in doc['humans']:actor=rules.make_human(self.rng,ident,faction,level,old['pos'],doc)
            else:
                actor=monster_rules.make(self.rng,ident,level,old['pos']);actor['faction']=faction
            b['enemies'][n]=actor
            actor['awake']=self.rng.random()>=.25
            actor['sight']=5
        self.wake_enemies()
        self.check_faction_victory()

    def prepare_factions(self):
        b=self.battle
        if not b:return
        b.setdefault('entrance047',b['pos'][:])
        for actor in b.get('enemies',[]):
            if 'faction' in actor:continue
            ident=content.monster_id(actor)
            choices=[k for k,d in rules.catalog()['factions'].items() if ident in d['members']]
            # Ordinary and infected variants share art, but have different allegiances.
            if 'monsters' in choices and 'infected' in choices:
                actor['faction']='infected' if self.rng.random()<.15 else 'monsters'
            else:actor['faction']=self.rng.choice(choices) if choices else 'monsters'

    def hostile_to_player(self,actor):return rules.hostile(rules.faction_of(actor),'player')

    def shot_info(self,enemy):
        if not self.hostile_to_player(enemy):return False,'Дружня фракція',0
        return super().shot_info(enemy)

    def shoot(self,enemy_id):
        self.prepare_factions()
        result=super().shoot(enemy_id)
        if result:self.check_faction_victory()
        return result

    def enemy_xp(self,enemy):
        if enemy.get('human'):return max(1,round((20+8*enemy.get('level',1))*.6**max(0,self.level-enemy.get('level',1)-1)))
        return super().enemy_xp(enemy)

    def _finish_enemy(self,e,weapon=None):
        b=self.battle
        if not b or e not in b['enemies']:return
        npc_kill=getattr(self,'_faction_npc_kill',False)
        if not e.get('human') and not npc_kill:return super()._finish_enemy(e,weapon)
        b['enemies'].remove(e)
        b.setdefault('corpses',[]).append({k:copy.deepcopy(e[k]) for k in ('pos','kind','type_id','grade','human','corpse_sprite_id','faction') if k in e})
        b.setdefault('kills',[]).append({k:copy.deepcopy(e[k]) for k in ('kind','type_id','grade','level','human','faction') if k in e})
        if e.get('human'):b.setdefault('faction_loot',[]).extend(rules.human_loot(self.rng,e))
        if not npc_kill:self.gain_xp(self.enemy_xp(e))

    def check_faction_victory(self):
        b=self.battle
        if not b or any(self.hostile_to_player(e) for e in b['enemies']):return False
        if not b['enemies'] and not b.get('safe_exit047'):
            self.victory();return True
        if not b.get('safe_exit047'):
            b['safe_exit047']=True
            b['exit']=b.get('exit',b.get('entrance047',b['pos']))[:]
            # A surviving ally must not block the exit cell.
            if any(e['pos']==b['exit'] for e in b['enemies']):b['exit']=b['pos'][:]
            b['cleared']=True
            self.log('Залишилися лише союзники. Дістаньтеся зеленої точки виходу, щоб забрати здобич без штрафу «Боягуз».')
            self.emit('Безпечний вихід відкрито',color='#9cdda8')
        return True

    def victory(self):
        b=self.battle
        if b and b['enemies']:
            self.check_faction_victory();return
        return super().victory()

    def battle_move(self,target):
        b=self.battle
        if not b:return False
        self.prepare_factions();self.check_faction_victory()
        if self.battle is not b:return False
        if b.get('safe_exit047') and list(target)==b['pos']==b['exit']:return self.flee()
        result=super().battle_move(target)
        if result and b.get('safe_exit047') and b['pos']==b['exit']:self.flee()
        return result

    def flee(self):
        b=self.battle
        if b:
            self.prepare_factions()
            if b.get('enemies') and not any(self.hostile_to_player(e) for e in b['enemies']):self.check_faction_victory()
        if b and b.get('safe_exit047'):
            if b['pos']!=b['exit']:self.log('Для безпечного виходу дістаньтеся зеленої точки.');return False
            # Use the existing reward pipeline without making surviving allies kills.
            survivors=b['enemies'];b['enemies']=[]
            dungeon=b.pop('dungeon',None)
            try:super().victory()
            finally:
                b['enemies']=survivors
                if dungeon:b['dungeon']=dungeon
            if self.battle is None:self._last_battle=copy.deepcopy(b)
            return self.battle is None
        return super().flee()

    def wake_enemies(self,pos=None):
        b=self.battle
        if not b:return
        self.prepare_factions()
        for actor in b.get('enemies',[]):
            if actor.get('awake',not b.get('dungeon')):continue
            targets=[e['pos'] for e in b['enemies'] if e is not actor and rules.hostile(rules.faction_of(actor),rules.faction_of(e))]
            if self.hostile_to_player(actor):targets.append(pos if pos is not None else b['pos'])
            if any(hexgrid.distance(actor['pos'],target)<=actor.get('sight',5) and hexgrid.visible(tuple(actor['pos']),tuple(target),b['walls']) for target in targets):actor['awake']=True

    def faction_turn(self):
        b=self.battle
        if not b:return
        self.prepare_factions()
        self.wake_enemies()
        if self.check_faction_victory():
            if self.battle:b['ap']=self.max_ap
            return
        for actor in list(b['enemies']):
            if actor not in b['enemies'] or not actor.get('awake',not b.get('dungeon')):continue
            candidates=[e for e in b['enemies'] if e is not actor and rules.hostile(rules.faction_of(actor),rules.faction_of(e))]
            player=dict(id='player',pos=b['pos'],defense=self.defense,resists={})
            if self.hostile_to_player(actor):candidates.append(player)
            if not candidates:continue
            # Prefer reachable targets, then distance; other creatures block movement.
            walls=set(map(tuple,b['walls']))
            def distance(target):
                blocked=walls|{tuple(e['pos']) for e in b['enemies'] if e is not actor and e is not target}
                if target is not player:blocked.add(tuple(b['pos']))
                route=hexgrid.path_to(tuple(actor['pos']),tuple(target['pos']),b['w'],b['h'],blocked)
                return (len(route) if route is not None else 100000,hexgrid.distance(actor['pos'],target['pos']))
            target=min(candidates,key=distance)
            regen=actor.get('regen',content.MONSTER_DATA.get(actor.get('type_id'),{}).get('regen',0))
            actor['hp']=min(actor['max_hp'],actor['hp']+regen)
            motion=[actor['pos'][:]]
            for _ in range(actor['speed']):
                if hexgrid.distance(actor['pos'],target['pos'])<=actor['range'] and hexgrid.visible(tuple(actor['pos']),tuple(target['pos']),b['walls']):break
                blocked=walls|{tuple(e['pos']) for e in b['enemies'] if e is not actor and e is not target}
                if target is not player:blocked.add(tuple(b['pos']))
                route=hexgrid.path_to(tuple(actor['pos']),tuple(target['pos']),b['w'],b['h'],blocked)
                if not route or route[0]==tuple(target['pos']):break
                actor['pos']=list(route[0]);motion.append(actor['pos'][:])
                self.wake_enemies()
            self.emit_move(motion,actor['id'])
            if hexgrid.distance(actor['pos'],target['pos'])>actor['range'] or not hexgrid.visible(tuple(actor['pos']),tuple(target['pos']),b['walls']):continue
            self.faction_attack(actor,target,target is player)
            if self.battle is not b:return
            if self.check_faction_victory():break
        if self.battle is b:
            b['ap']=self.max_ap;b['max_ap']=self.max_ap;b['round']+=1

    def faction_attack(self,actor,target,is_player):
        from combat033 import projectile_components
        weapon=actor.get('equipment',{}).get('weapon')
        self.emit(kind='attack' if actor['range']>1 else 'slash',pos=target['pos'],source=actor['pos'],color='#ff976f')
        evasion=self.protection_stat('evasion') if is_player else sum(p.stats(i).get('evasion',0) for i in target.get('equipment',{}).values())
        if self.rng.randrange(100)<min(45,evasion):self.emit('Ухилення',pos=target['pos']);return
        if weapon:
            if self.rng.randrange(100)>=min(98,max(1,p.stats(weapon).get('accuracy',75))):self.emit('Промах',pos=target['pos']);return
            # Share weapon/module damage and target resistance formulas with the player.
            shot=copy.deepcopy(weapon);shot['stats']['attack']+=actor['attack']-p.stats(weapon).get('attack',0)
            critical=self.rng.randrange(100)<min(65,5+p.stats(weapon).get('crit',0))
            damage=sum(projectile_components(shot,actor['level'],target,self.rng.randint(-2,2),critical).values())
            weapon['durability']=max(0,round(p.mr.condition(weapon)-.6*max(.1,1-p.mr.aggregate(weapon).get('strength',0)/100),2))
        else:damage=balance.damage(actor['damage']+self.rng.randint(-2,2),actor.get('attack',0),target.get('defense',0))
        if is_player:
            reflected=p.mr.chance(self.protection_stat('reflect_percent'))
            if reflected and self.rng.random()*100<reflected:
                actor['hp']-=damage;self.emit(f'Відбиття: −{damage}',pos=actor['pos'])
                if actor['hp']<=0:self._finish_enemy(actor)
                return
            damage=self.incoming_combat_damage(damage);self.hp-=damage
            self.test_armor_hit(damage)
            self.wear(self.equipped['armor'],.5);self.wear(self.equipped['helmet'],.25)
        else:
            reflected=p.mr.chance(sum(p.stats(i).get('reflect_percent',0) for k,i in target.get('equipment',{}).items() if k!='weapon'))
            if reflected and self.rng.random()*100<reflected:
                actor['hp']-=damage;self.emit(f'Відбиття: −{damage}',pos=actor['pos'])
                if actor['hp']<=0:
                    self._faction_npc_kill=True
                    try:self._finish_enemy(actor)
                    finally:self._faction_npc_kill=False
                return
            target['hp']-=damage;target['awake']=True
        self.emit(f'−{damage}',pos=target['pos'],color='#ff8f79')
        self.log(f'{actor["name"]} → '+('Гравець' if is_player else target['name'])+f': −{damage} HP.')
        if is_player and self.hp<=0:self.defeat()
        elif not is_player and target['hp']<=0:
            self._faction_npc_kill=True
            try:self._finish_enemy(target)
            finally:self._faction_npc_kill=False
