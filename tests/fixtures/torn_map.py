"""Assemble a torn map through the public game methods, like a player would."""


def solve_map(g,ident):
    state=g.map_puzzle(ident);cols=state['cols']
    for i in range(len(state['pieces'])):
        for _ in range(4):
            if state['pieces'][i][2]==0:break
            assert g.map_rotate(ident,i)
        if g.map_quest(ident) is None or state is not g.map_puzzle(ident) or _solved(g,ident):break
        assert g.map_move(ident,i,1+i%cols,.8+i//cols)
        if _solved(g,ident):break
    return state


def _solved(g,ident):
    q=g.map_quest(ident)
    return q is None or q.get('map_solved')
