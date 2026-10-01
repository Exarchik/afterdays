"""Validated dialogue trees and transactional, isolated dialogue sessions."""
import copy,re
TYPES={'bool':'Так / ні','int':'Ціле число','str':'Текст'}
OPS={'==':'дорівнює','!=':'не дорівнює','>=':'не менше','<=':'не більше','>':'більше','<':'менше'}
REWARDS={'money':'Кредити','xp':'Досвід','parts':'Запчастини','fragments':'Фрагменти','food':'Їжа','med':'Аптечки','rad':'Радіопротектори','repairkit':'Ремкомплекти','ammo':'Пістолетні набої','gear':'Спорядження','heal':'Здоров’я'}

def parse_value(text,kind):
    if kind=='bool':
        if str(text).lower() not in ('true','false','так','ні','1','0'):raise ValueError('Введіть так або ні.')
        return str(text).lower() in ('true','так','1')
    if kind=='int':return int(text)
    return str(text)

def typed(value,kind):return type(value) is {'bool':bool,'int':int,'str':str}.get(kind)

def conditions_met(conditions,values):
    def check(c):
        a,b=values[c['variable']],c['value'];op=c['op']
        return a==b if op=='==' else a!=b if op=='!=' else a>=b if op=='>=' else a<=b if op=='<=' else a>b if op=='>' else a<b
    return all(check(c) for c in conditions)

def node(actor='player',text='Нова фраза'):
    return dict(actor=actor,text=text,next=None,replies=[])

def validate(doc,art=None,quests=None):
    errors=[]
    def need(ok,text):
        if not ok:errors.append(text)
    if not isinstance(doc,dict) or doc.get('version')!=1:return ['Некоректний каталог діалогів.']
    actors=doc.get('actors',{});variables=doc.get('variables',{});dialogs=doc.get('dialogues',[])
    if not isinstance(actors,dict) or not isinstance(variables,dict) or not isinstance(dialogs,list):return ['Некоректна структура каталогу.']
    need('player' in actors,'Потрібен актор Головний герой.')
    def identifier(value):return isinstance(value,str) and bool(re.fullmatch('[a-z][a-z0-9_]*',value))
    for key,a in actors.items():
        need(identifier(key) and isinstance(a,dict),'Некоректний актор.')
        if not isinstance(a,dict):continue
        need(isinstance(a.get('name'),str) and bool(a['name'].strip()),'Актор: порожнє ім’я.')
        need(isinstance(a.get('art'),str) and (art is None or a['art'] in art),'Актор: невідомий арт.')
    for key,v in variables.items():
        need(identifier(key) and isinstance(v,dict),'Некоректна змінна.')
        if isinstance(v,dict):need(v.get('type') in TYPES and typed(v.get('default'),v.get('type')),'Змінна '+key+': тип/початкове значення.')
    def conditions(rows):
        if not isinstance(rows,list):errors.append('Умови мають бути списком.');return
        for c in rows:
            if not isinstance(c,dict):errors.append('Некоректна умова.');continue
            v=variables.get(c.get('variable'),{})
            need(c.get('op') in OPS and typed(c.get('value'),v.get('type')),'Некоректна умова/значення змінної.')
            need(c.get('op') in ('==','!=') or v.get('type')=='int','Порівняння більше/менше дозволене лише для чисел.')
    def actions(rows):
        if not isinstance(rows,list):errors.append('Дії мають бути списком.');return
        for a in rows:
            if not isinstance(a,dict):errors.append('Некоректна дія.');continue
            kind=a.get('kind')
            if kind in ('set','add'):
                v=variables.get(a.get('variable'),{})
                need(typed(a.get('value'),v.get('type')) and (kind!='add' or v.get('type')=='int'),'Дія: некоректна змінна або тип.')
            elif kind=='reward':need(a.get('reward') in REWARDS and type(a.get('amount')) is int and 1<=a['amount']<=1000000,'Некоректна нагорода.')
            elif kind=='quest':need(isinstance(a.get('quest'),str) and (quests is None or a['quest'] in quests),'Дія посилається на невідомий квест.')
            else:errors.append('Невідомий тип дії.')
    ids=[]
    for d in dialogs:
        if not isinstance(d,dict):errors.append('Некоректний діалог.');continue
        ident=d.get('id');need(identifier(ident) and ident not in ids,'ID діалогу порожній або повторюється.');ids.append(ident)
        need(isinstance(d.get('title'),str) and bool(d['title'].strip()),'Порожня назва діалогу.')
        conditions(d.get('conditions',[]));nodes=d.get('nodes',{})
        if not isinstance(nodes,dict) or d.get('root') not in nodes:errors.append('Діалог: немає початкового блоку.');continue
        edges={};reply_ids=set()
        for key,n in nodes.items():
            if not identifier(key) or not isinstance(n,dict):errors.append('Некоректний блок.');continue
            need(n.get('actor') in actors,'Блок: невідомий актор.');need(isinstance(n.get('text'),str) and bool(n['text'].strip()),'Блок: порожня фраза.')
            replies=n.get('replies',[])
            if not isinstance(replies,list):errors.append('Відповіді мають бути списком.');continue
            need(not replies or n.get('actor')!='player','Блок героя не може мати варіантів відповідей.')
            need(not replies or n.get('next') is None,'Блок із відповідями не може мати автоматичного переходу.')
            edges[key]=[n['next']] if n.get('next') else []
            for r in replies:
                if not isinstance(r,dict):errors.append('Некоректна відповідь.');continue
                need(identifier(r.get('id')) and r.get('id') not in reply_ids,'ID відповіді повторюється.');reply_ids.add(r.get('id'))
                need(isinstance(r.get('text'),str) and bool(r['text'].strip()),'Порожня відповідь.')
                conditions(r.get('conditions',[]));actions(r.get('actions',[]))
                if r.get('next'):edges[key].append(r['next'])
        if any(target not in nodes for links in edges.values() for target in links):errors.append('Перехід веде до відсутнього блоку.');continue
        seen=set()
        def visit(key):
            if key in seen:return False
            seen.add(key)
            return all(visit(k) for k in edges.get(key,[]))
        need(visit(d['root']) and seen==set(nodes),'Блоки мають утворювати одне дерево без циклів і відірваних гілок.')
    return errors

class Session:
    def __init__(self,document,dialogue_id,quests=None,game=None,player_name='Головний герой',player_art=None):
        errors=validate(document,quests=quests)
        if errors:raise ValueError('\n'.join(errors))
        self.doc=copy.deepcopy(document);self.quests=copy.deepcopy(quests or {});self.game=game
        saved=game.reputation_state.get('dialogue_state',{}) if game else {}
        self.values={k:copy.deepcopy(v['default']) for k,v in self.doc['variables'].items()}
        self.values.update({k:v for k,v in saved.get('variables',{}).items() if k in self.doc['variables'] and typed(v,self.doc['variables'][k]['type'])})
        self.claimed=set(saved.get('claimed',[]));self.rewards={};self.started=[];self.history=[]
        self.player_name=getattr(game,'player_name',player_name) if game else player_name
        self.player_art=getattr(game,'player_art',player_art) if game else player_art
        self.switch(dialogue_id)
    def switch(self,ident):
        d=next(d for d in self.doc['dialogues'] if d['id']==ident)
        if not conditions_met(d.get('conditions',[]),self.values):raise ValueError('Умови доступності діалогу не виконані.')
        self.dialogue=d;self.current=d['root']
    @property
    def block(self):return self.dialogue['nodes'].get(self.current)
    def actor(self):
        if not self.block:return None
        key=self.block['actor'];actor=copy.deepcopy(self.doc['actors'][key])
        if key=='player':actor.update(name=self.player_name,art=self.player_art or actor['art'])
        return actor
    def replies(self):return [r for r in self.block.get('replies',[]) if conditions_met(r.get('conditions',[]),self.values)] if self.block else []
    def choose(self,reply_id=None):
        n=self.block
        if not n:raise ValueError('Діалог завершено.')
        r=next((r for r in self.replies() if r['id']==reply_id),None) if reply_id else None
        if n.get('replies') and r is None:raise ValueError('Ця відповідь недоступна.')
        if reply_id and r is None:raise ValueError('Невідома відповідь.')
        values=copy.deepcopy(self.values);rewards=dict(self.rewards);started=list(self.started);claimed=set(self.claimed)
        simulated=copy.deepcopy(self.game) if self.game else None
        token=self.dialogue['id']+':'+self.current+':'+r['id'] if r else None
        if r and token not in claimed:
            for a in r.get('actions',[]):
                if a['kind']=='set':values[a['variable']]=a['value']
                elif a['kind']=='add':values[a['variable']]+=a['value']
                elif a['kind']=='reward':
                    rewards[a['reward']]=rewards.get(a['reward'],0)+a['amount']
                    if simulated:
                        import event_runtime
                        for _ in range(a['amount'] if a['reward']=='gear' else 1):
                            event_runtime.apply(simulated,dict(kind=a['reward'],amount=a['amount'],destination='bag',ammo='pistol'),{'title':self.dialogue['title']})
                elif a['kind']=='quest':
                    if a['quest'] not in self.quests:raise ValueError('Квест більше не існує.')
                    if simulated:
                        existing=next((q for q in simulated.quests if q.get('authored_id')==a['quest'] and q['status']=='active'),None)
                        if not existing:
                            offer=next((q for q in simulated.mayor_offers() if q.get('authored_id')==a['quest']),None)
                            if not offer or not simulated.accept_quest(offer['id']):raise ValueError('Квест зараз не можна прийняти: перевірте місто, умови та ліміт квестів.')
                    if a['quest'] not in started:started.append(a['quest'])
            claimed.add(token)
        if simulated:
            simulated.reputation_state['dialogue_state']=dict(variables=values,claimed=sorted(claimed))
            self.game.__dict__.clear();self.game.__dict__.update(simulated.__dict__)
        self.values,self.rewards,self.started,self.claimed=values,rewards,started,claimed
        self.history.append((self.actor()['name'],n['text'],r['text'] if r else ''))
        self.current=r.get('next') if r else n.get('next')
