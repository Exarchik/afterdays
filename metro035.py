"""Persistent multi-stage metro restoration using existing quest minigames."""
import copy
import math
import afterdays as r
import update033
import progression as p
from i18n import t as tr

KINDS=('archive','generator','radio','dungeon','hermit','cache')

class Game(update033.Game):
    def metro_parent(self,ident):
        """Resolve a chain or one of its nested stage IDs without creating extra journal quests."""
        return next((q for q in self.quests if q.get('metro_chain') and (q['id']==ident or any(s['id']==ident for s in q['metro_chain']['steps']+[q['metro_chain']['station']]))),None)

    def metro_step(self,q):
        """Return the current saved stage, or the final station installation."""
        chain=q['metro_chain'];index=chain['index']
        return chain['steps'][index] if index<len(chain['steps']) else chain['station']

    def metro_plan(self,q):
        """Choose two to five stages and reachable targets before accepting the contract."""
        pool=self.quest_locations(q)
        if not pool:return None
        areas=self.area_candidates(q)
        origin=self.cities[q['city']];reachable=self.player_reachable_world(origin)
        minimum=3 if q['level']>=3 else 1
        cities=[pos for pos in self.cities[:self.main_city_count] if tuple(pos) in reachable and math.dist(pos,origin)<=25 and minimum<=self.region_at(*pos)<=q['level']+1]
        available=[k for k in KINDS if (k!='cache' or areas) and (k!='archive' or cities)]
        last=self.rng.choice(['dungeon']+(['cache'] if areas else []))
        types=self.rng.sample([k for k in available if k!=last],self.rng.randint(1,min(4,len(available)-1)))+[last]
        steps=[]
        for n,kind in enumerate(types):
            choices=cities if kind=='archive' else areas if kind=='cache' else ([pos for pos in pool if self.world[pos[1]][pos[0]]=='waste'] or pool) if kind=='hermit' else pool
            pos=list(self.rng.choice(choices))
            s=dict(id=r.uid(),kind={'archive':'torn_map','dungeon':'purge','hermit':'metro_hermit'}.get(kind,kind),metro_role=kind,metro_parent=q['id'],city=q['city'],level=q['level'],zone=q['level'],unique=True,status='active',title=q['title'],progress=0,goal=1,pos=pos,target_kind=None)
            if kind=='archive':
                layout=list(range(9))
                while layout==list(range(9)):self.rng.shuffle(layout)
                s.update(layout=layout,map_solved=False,received=False)
            elif kind=='generator':
                self.init_generator(s);s.update(material=self.rng.choice(['parts','fragments']),material_qty=self.rng.randint(2,6))
            elif kind=='radio':s.update(radio_target=[self.rng.randint(2,18) for _ in range(3)],radio_values=[10]*3,radio_attempts=0)
            elif kind=='cache':
                x,y=pos;s.update(area=[x-1,y-1,x+1,y+1],cache_pos=[self.rng.randint(x-1,x+1),self.rng.randint(y-1,y+1)],searched_cells=[])
            elif kind=='dungeon':s['dungeon_kind']=tr('metro035.vault')
            elif kind=='hermit':s.update(task=self.rng.choice(['food','med','parts','hunt']),need=self.rng.randint(2,5),kills=0,talked=False)
            steps.append(s)
        station=dict(id=r.uid(),kind='purge',metro_role='station',metro_parent=q['id'],city=q['city'],level=q['level'],zone=q['level'],unique=True,status='active',title=q['title'],progress=0,goal=1,pos=list(origin),dungeon_kind=tr('metro035.station'))
        return dict(steps=steps,index=0,station=station,broken=self.rng.random()<.35,infested=self.rng.random()<.4,installed=False,history=[])

    def accept_quest(self,ident):
        """Accept new metro jobs as one chain; existing accepted jobs retain their progress."""
        offer=next((q for q in self.mayor_offers() if q['id']==ident and q['status']=='offered'),None)
        if not offer or 'metro_city' not in offer:return super().accept_quest(ident)
        if self.battle or self.road_event or sum(q['status']=='active' for q in self.quests)>=8:return False
        q=copy.deepcopy(offer);chain=self.metro_plan(q)
        if not chain:self.log(tr('exp.no_location'));return False
        q.update(status='active',metro_chain=chain,progress=0,goal=1)
        self.quests.append(q);offer.update(status='accepted',seen=True);self.metro_sync(q)
        self.log(tr('metro035.accepted',count=len(chain['steps'])));return True

    def metro_sync(self,q):
        """Expose only the current stage marker and its search area to map rendering."""
        s=self.metro_step(q);q['pos']=s['pos'][:];q.pop('area',None);q.pop('searched_cells',None)
        if s.get('area'):q['area']=s['area'][:]
        self.reveal(*q['pos'],0)

    def metro_local(self):
        """Find active chains whose current objective is accessible at the player's position."""
        if self.battle or self.road_event:return []
        result=[]
        for q in self.quests:
            if not q.get('metro_chain') or q['status']!='active' or q['metro_chain']['installed']:continue
            s=self.metro_step(q);here=s['pos']==[self.x,self.y]
            if s.get('area'):
                a,b,c,d=s['area'];here=a<=self.x<=c and b<=self.y<=d
            if here:result.append(q)
        return result

    def metro_part(self,q):
        """Find the actual carried station component, excluding map and clue tokens."""
        return next((i for i in self.bag if i.get('quest_id')==q['id'] and i.get('metro_component')),None)

    def metro_advance(self,s):
        """Complete a stage once and reveal the next objective or grant the component."""
        q=self.metro_parent(s['id'])
        if not q or self.metro_step(q) is not s or s.get('completed'):return
        chain=q['metro_chain'];s.update(progress=1,completed=True)
        chain['history'].append(tr('metro035.stage_'+s['metro_role']))
        self.clear_quest_items(s['id']);chain['index']+=1
        if chain['index']==len(chain['steps']):
            part=dict(id=r.uid(),type_id='quest_item',kind='quest',quest_id=q['id'],metro_component=True,quest_repair=True,name=q['part_name'],art_id='metro_component',rarity=1,weight=0,value=max(50,round(70*q['level']**1.3)),durability=float(self.rng.randint(0,50) if chain['broken'] else 100))
            self.bag.append(part);self.log(tr('metro035.found',name=part['name'],condition=round(part['durability'])))
        else:self.log(tr('metro035.next',number=chain['index']+1,count=len(chain['steps'])))
        self.metro_sync(q);self.emit(tr('metro035.stage_done'),color='#99dca5')

    def local_expedition(self):
        """Let existing generator and lock logic operate on nested metro stages."""
        for q in self.metro_local():
            s=self.metro_step(q)
            if s['kind'] in ('generator','cache'):return s
        return super().local_expedition()

    def destination_quest(self):
        """Expose a local metro relay to the existing radio minigame."""
        for q in self.metro_local():
            s=self.metro_step(q)
            if s['kind']=='radio':return s
        return super().destination_quest()

    def map_quest(self,ident):
        """Expose only a received, current archive map to the puzzle UI."""
        q=self.metro_parent(ident)
        if q and q['status']=='active':
            s=self.metro_step(q)
            if s['id']==ident and s['kind']=='torn_map' and s.get('received'):return s
        return super().map_quest(ident)

    def swap_map_pieces(self,ident,a,b):
        """Solve archive maps without opening an unrelated standalone treasure quest."""
        q=self.metro_parent(ident)
        if not q:return super().swap_map_pieces(ident,a,b)
        s=self.map_quest(ident)
        if self.battle or self.road_event or not s or s['map_solved'] or any(type(v)!=int or not 0<=v<9 for v in (a,b)):return False
        s['layout'][a],s['layout'][b]=s['layout'][b],s['layout'][a]
        if s['layout']==list(range(9)):
            s['map_solved']=True;self.metro_advance(s)
            s['pos']=q['pos'][:] # The completed puzzle displays the newly revealed coordinates.
        return True

    def repair_generator(self,ident):
        """Advance only after the generator puzzle and material payment succeed."""
        q=self.metro_parent(ident);s=self.metro_step(q) if q else None
        ok=super().repair_generator(ident)
        if ok and s:self.metro_advance(s)
        return ok

    def tune_radio(self,ident,values):
        """Advance after tuning the relay; retain the old stage for its open UI."""
        q=self.metro_parent(ident);s=self.metro_step(q) if q else None
        ok=super().tune_radio(ident,values)
        if ok and s:self.metro_advance(s)
        return ok

    def unlock_cache(self,ident,angle):
        """Replace the intermediate parcel with a clue or the final metro component."""
        q=self.metro_parent(ident);s=self.metro_step(q) if q else None
        ok=super().unlock_cache(ident,angle)
        if ok and s:self.metro_advance(s)
        return ok

    def metro_action(self,ident):
        """Perform the current archive, hermit, dungeon or station interaction."""
        q=next((q for q in self.metro_local() if q['id']==ident),None)
        if not q:return False
        s=self.metro_step(q);kind=s['metro_role']
        if kind=='archive':
            if not s['received']:
                s['received']=True;self.bag.append(self.quest_token(s,'torn_map_item'))
            self._metro_map_request=s['id'];return True
        if kind=='hermit':
            if not s['talked']:
                s['talked']=True;self.log(tr('metro035.help_started'));return True
            if s['task']=='hunt':
                if s['kills']<s['need']:self.log(tr('metro035.help_missing'));return False
            else:
                if self.count(s['task'])<s['need']:self.log(tr('metro035.help_missing'));return False
                self.consume(s['task'],s['need'])
            self.metro_advance(s);return True
        if kind=='station':
            part=self.metro_part(q)
            if not part or part['durability']<100:self.log(tr('metro035.repair_first'));return False
            if not q['metro_chain']['infested']:
                q['metro_chain']['installed']=True;q['progress']=1;self.log(tr('metro035.installed'));return True
        if kind in ('dungeon','station'):
            if s.get('dungeon_state'):
                self.battle=copy.deepcopy(s['dungeon_state']);self.battle['pos']=self.battle['exit'][:]
                self.battle['ap']=self.max_ap;self.quest_battle=s['id']
            else:
                self.start_dungeon(s);self.battle['metro_stage']=s['id'];self.battle['metro_station']=kind=='station'
            return True
        return self.search()

    def monster_killed(self,enemy,xp,weapon):
        """Count a hermit's requested nearby kills only after speaking to them."""
        super().monster_killed(enemy,xp,weapon)
        for q in self.quests:
            if q.get('metro_chain') and q['status']=='active':
                s=self.metro_step(q)
                if s['metro_role']=='hermit' and s['task']=='hunt' and s['talked'] and math.dist(s['pos'],(self.x,self.y))<=10:
                    s['kills']=min(s['need'],s['kills']+1)

    def metro_chest(self):
        """Grant the dungeon clue or install the component at the cleared station chest."""
        b=self.battle
        if not b or not b.get('metro_stage') or not b['cleared']:return False
        import hexgrid
        if hexgrid.distance(b['pos'],b['chest'])>1:return False
        q=self.metro_parent(b['metro_stage'])
        if not q:return False
        s=next(s for s in q['metro_chain']['steps']+[q['metro_chain']['station']] if s['id']==b['metro_stage'])
        if s['metro_role']=='station':
            part=self.metro_part(q)
            if not part or part['durability']<100 or q['metro_chain']['installed']:return False
            q['metro_chain']['installed']=True;q['progress']=1;self.log(tr('metro035.installed'))
        elif not s.get('completed'):self.metro_advance(s)
        return True

    def search(self):
        """Route metro objectives before generic search and preserve dungeon progress on exit."""
        b=self.battle
        if b and b.get('metro_stage'):
            if b.get('metro_exit_paid') and b['cleared'] and b['pos']==b['exit']:
                self.battle=None;self.quest_battle=None;self.metro_preserve(b);return True
            changed=self.metro_chest();ok=super().search();self.metro_preserve(b)
            return changed or ok
        local=self.metro_local()
        if local:
            q=local[0];s=self.metro_step(q)
            if s['metro_role'] in ('archive','hermit','dungeon','station'):return self.metro_action(q['id'])
        ok=super().search()
        for q in local:
            s=self.metro_step(q)
            if s.get('area'):q['searched_cells']=s.get('searched_cells',[])[:]
        return ok

    def metro_preserve(self,b):
        """Persist uncleared/revisitable metro dungeons so exiting cannot reroll their rewards."""
        if b and b.get('metro_stage') and self.battle is None:
            if b['cleared']:b['metro_exit_paid']=True
            q=self.metro_parent(b['metro_stage'])
            if q:
                for s in q['metro_chain']['steps']+[q['metro_chain']['station']]:
                    if s['id']==b['metro_stage']:s['dungeon_state']=copy.deepcopy(b)

    def flee(self):
        """Preserve the station or vault when the player leaves through its entrance."""
        b=self.battle
        if b and b.get('metro_stage') and b.get('metro_exit_paid') and b['cleared'] and b['pos']==b['exit']:
            self.battle=None;self.quest_battle=None;self.metro_preserve(b);return True
        ok=super().flee()
        if ok:self.metro_preserve(b)
        return ok

    def quest_ready(self,q):
        """A metro chain becomes ready only after installation, never after an intermediate task."""
        if q.get('metro_chain'):return q['status']=='active' and q['metro_chain']['installed'] and self.metro_part(q) is not None
        if q.get('metro_parent'):return q.get('completed',False)
        return super().quest_ready(q)

    def quest_item_views(self,q):
        """Show the component's actual repair condition and any currently required supplies."""
        if not q.get('metro_chain'):return super().quest_item_views(q)
        items=[self.metro_part(q) or dict(id='metro-preview',kind='quest',name=q['part_name'],art_id='metro_component',rarity=1,weight=0,value=0)]
        s=self.metro_step(q)
        if s['metro_role']=='generator':items.append(p.parts(s['material_qty']) if s['material']=='parts' else p.fragments(s['material_qty']))
        if s['metro_role']=='hermit' and s['task']!='hunt':items.append(p.parts(s['need']) if s['task']=='parts' else p.supply(s['task'],s['need']))
        return items

    def abandon_quest(self,ident):
        """Remove nested map/parcel tokens as well as the parent contract when abandoning."""
        q=self.metro_parent(ident);nested=[s['id'] for s in q['metro_chain']['steps']] if q else []
        ok=super().abandon_quest(ident)
        if ok:
            for sid in nested:self.clear_quest_items(sid)
        return ok

    def quest_text(self,q):
        """Describe the active stage, completed history, repair needs and final return."""
        if 'metro_city' in q and q['status']=='offered':return super().quest_text(q)+'\n\n'+tr('metro035.offer')
        if not q.get('metro_chain'):return super().quest_text(q)
        c=q['metro_chain'];s=self.metro_step(q)
        lines=[q['title']+' · '+self.city_name(q['city']),tr('metro035.progress',done=min(c['index'],len(c['steps'])),total=len(c['steps']))]
        if q['status']=='done':lines.append(tr('metro035.done'))
        elif c['installed']:lines.append(tr('metro035.return'))
        else:
            lines.append(tr('metro035.stage_'+s['metro_role']));lines.append(tr('metro035.desc_'+s['metro_role']))
            if s['metro_role']=='hermit':lines.append(tr('metro035.help_'+s['task'],need=s['need'],kills=s['kills']))
            if s['metro_role']=='generator':lines.append(tr('exp.material',name=p.parts(1)['name'] if s['material']=='parts' else p.fragments(1)['name'],qty=s['material_qty']))
            part=self.metro_part(q)
            if part and part['durability']<100:lines.append(tr('metro035.repair_state',value=round(part['durability'])))
            if s['metro_role']=='station':lines.append(tr('metro035.infested') if c['infested'] else tr('metro035.peaceful'))
            lines.append(tr('exp.point',x=s['pos'][0],y=s['pos'][1]))
        if c['history']:lines.append(tr('metro035.history')+'\n'+'\n'.join('✓ '+v for v in c['history']))
        lines.append(tr('metro035.reward',level=q['level'],money=q['reward'],xp=q['xp_reward']))
        return '\n\n'.join(lines)
