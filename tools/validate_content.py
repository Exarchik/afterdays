"""Validate editable content and translation references without starting Tk."""
import ast,json,re,string,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import content,i18n

def validate():
    errors=[]
    for title,data in [('equipment',content.EQUIPMENT),('modules',content.MODULE_DATA),('monsters',content.MONSTER_DATA),('consumables',content.CONSUMABLES)]:
        for ident,definition in data.items():
            if not re.fullmatch('[a-z][a-z0-9_]*',ident):errors.append(f'Invalid ID: {ident}')
            if ident+'.name' not in i18n.FALLBACK:errors.append(f'Missing name: {ident}')
            if ident+'.description' not in i18n.FALLBACK:errors.append(f'Missing description: {ident}')
    for path in ROOT.glob('*.py'):
        if path.name.startswith('test_'):continue
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='tr' and node.args and isinstance(node.args[0],ast.Constant):
                key=node.args[0].value
                if key not in i18n.FALLBACK:errors.append(f'{path.name}: missing {key}')
    fmt=string.Formatter()
    def fields(text):return {field for _,field,_,_ in fmt.parse(text) if field is not None}
    for folder in (ROOT/'locales').iterdir():
        if not folder.is_dir() or folder.name=='uk':continue
        for key,value in i18n.catalog(folder.name).items():
            if key not in i18n.FALLBACK:errors.append(f'{folder.name}: unknown key {key}');continue
            try:
                if fields(value)!=fields(i18n.FALLBACK[key]):errors.append(f'{folder.name}: placeholder mismatch {key}')
            except ValueError:errors.append(f'{folder.name}: malformed template {key}')
    return errors
if __name__=='__main__':
    errors=validate()
    for error in errors:print(error)
    print(f'Content validation: {len(errors)} error(s)')
    raise SystemExit(bool(errors))
