"""Sequential story modules, with immutable accepted definitions in save data."""
import copy
import re


def validate(document, dialogues=None):
    stories=document.get('stories',[]);errors=[]
    if not isinstance(stories,list):return ['Сюжетні лінії мають бути списком.']
    quests={q['id']:q for q in document['quests']};ids=set();used=set()
    dialog_ids={d['id'] for d in dialogues['dialogues']} if dialogues is not None else None
    for story in stories:
        if not isinstance(story,dict):errors.append('Некоректна сюжетна лінія.');continue
        ident=story.get('id')
        if not isinstance(ident,str) or not re.fullmatch('[a-z][a-z0-9_]*',ident) or ident in ids:
            errors.append('Некоректний або повторний ID сюжету.');continue
        ids.add(ident)
        if not isinstance(story.get('title'),str) or not story['title'].strip():errors.append(ident+': потрібна назва.')
        if type(story.get('enabled')) is not bool:errors.append(ident+': потрібен перемикач доступності.')
        if 'start_after_moves' in story and (type(story['start_after_moves']) is not int or story['start_after_moves']<1):errors.append(ident+': кількість кроків має бути додатним цілим числом.')
        stages=story.get('stages')
        if not isinstance(stages,list) or not stages:errors.append(ident+': додайте етапи.');continue
        for stage in stages:
            if not isinstance(stage,dict):errors.append(ident+': некоректний етап.');continue
            kind=stage.get('kind');ref=stage.get('ref')
            if kind=='quest':
                if not isinstance(ref,str) or ref not in quests or ref in used:
                    errors.append(ident+': квест відсутній або вже використаний у сюжеті.')
                else:
                    used.add(ref)
                    if quests[ref]['repeatable']:errors.append(ident+': сюжетний квест має бути одноразовим.')
            elif kind=='dialogue':
                if not isinstance(ref,str) or not ref or (dialog_ids is not None and ref not in dialog_ids):errors.append(ident+': невідомий діалог.')
            elif kind=='visit':
                if type(ref) is not int or ref<0:errors.append(ident+': ID міста має бути невід’ємним числом.')
            else:errors.append(ident+': невідомий тип етапу.')
    return errors


class StoryMixin:
    def prepare_campaign(self):
        from campaign_intro import prepare
        prepare(self)

    def step(self,dx,dy):
        from campaign_intro import pending
        if pending(self):return False
        intro=self.reputation_state.get('campaign_intro');before=(self.x,self.y);battle=bool(self.battle)
        guided=getattr(self,'_guided_trip',False)
        if intro and intro['moves']<2:self._guided_trip=True
        try:ok=super().step(dx,dy)
        finally:self._guided_trip=guided
        if ok and intro is not None and not battle and before!=(self.x,self.y):
            intro['moves']+=1
            import quest_catalog
            for spec in quest_catalog.DOCUMENT.get('stories',[]):
                if spec.get('start_after_moves') and intro['moves']>=spec['start_after_moves']:
                    if self.start_story(spec['id']):self.log('Головний квест: '+spec['title']+' · Рація оживає серед шуму вітру.')
        return ok

    def story_states(self):
        return self.reputation_state.setdefault('stories',{})

    def start_story(self,ident):
        import quest_catalog
        import content
        if self.battle or self.road_event or ident in self.story_states():return False
        spec=next((s for s in quest_catalog.DOCUMENT.get('stories',[]) if s['id']==ident and s['enabled']),None)
        if spec is None:return False
        if spec.get('start_after_moves') and self.reputation_state.get('campaign_intro',{}).get('moves',0)<spec['start_after_moves']:return False
        dialogs=content.read('dialogues.json')
        if validate(quest_catalog.DOCUMENT,dialogs):return False
        if any(s['kind']=='visit' and s['ref']>=len(self.cities) for s in spec['stages']):return False
        quests={q['id']:copy.deepcopy(q) for q in quest_catalog.DOCUMENT['quests']}
        self.story_states()[ident]=dict(definition=copy.deepcopy(spec),index=0,status='active',
            quests=quests,dialogues=dialogs,node=None,history=[])
        self.story_sync();return True

    def story_sync(self):
        for state in self.story_states().values():
            while state['status']=='active':
                step=state['definition']['stages'][state['index']]
                ready=(step['kind']=='quest' and any(q.get('authored_id')==step['ref'] and q['status']=='done' for q in self.quests))
                ready=ready or (step['kind']=='visit' and not self.battle and not self.road_event and self.city==step['ref'])
                if not ready:break
                self.story_advance(state)

    def story_advance(self,state):
        state['history'].append(state['index']);state['index']+=1;state['node']=None
        if state['index']==len(state['definition']['stages']):state['status']='done'

    def story_allows(self,quest_id):
        import quest_catalog
        self.story_sync()
        owned=any(s['kind']=='quest' and s['ref']==quest_id for story in quest_catalog.DOCUMENT.get('stories',[]) for s in story['stages'])
        for state in self.story_states().values():
            stages=state['definition']['stages']
            if any(s['kind']=='quest' and s['ref']==quest_id for s in stages):
                return state['status']=='active' and stages[state['index']]==dict(kind='quest',ref=quest_id)
        return not owned

    def authored_specs(self):
        import quest_catalog
        specs={q['id']:q for q in quest_catalog.DOCUMENT['quests']}
        for state in self.story_states().values():
            for stage in state['definition']['stages']:
                if stage['kind']=='quest':specs[stage['ref']]=state['quests'][stage['ref']]
        return list(specs.values())

    def story_session(self,ident):
        import dialogue_system
        self.story_sync();state=self.story_states().get(ident)
        if self.battle or self.road_event or not state or state['status']!='active':raise ValueError('Сюжетний діалог зараз недоступний.')
        step=state['definition']['stages'][state['index']]
        if step['kind']!='dialogue':raise ValueError('Поточний етап не є діалогом.')
        document=copy.deepcopy(state['dialogues'])
        # Entry conditions were already satisfied before the saved conversation began.
        if state['node'] is not None:
            next(d for d in document['dialogues'] if d['id']==step['ref'])['conditions']=[]
        session=dialogue_system.Session(document,step['ref'],state['quests'],self)
        session.story_context=(ident,state['index'])
        if state['node'] is not None:session.current=state['node']
        return session

    def abandon_quest(self,ident):
        q=next((q for q in self.quests if q['id']==ident),None)
        if q and any(s['kind']=='quest' and s['ref']==q.get('authored_id') for state in self.story_states().values() for s in state['definition']['stages']):return False
        return super().abandon_quest(ident)
