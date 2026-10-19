"""Solve a generator balance board through the real toggle API (negative switches first)."""
from game.systems import generator_balance as balance


def solution(q):
    lo,hi=q['generator_zone']
    return next(mask for mask,total in balance.subset_sums(q['generator_weights']) if lo<=total<=hi)


def solve(g,q):
    weights=q['generator_weights'];mask=solution(q)
    for i in sorted((i for i in range(len(weights)) if mask>>i&1),key=lambda i:weights[i]):
        assert g.generator_toggle(q['id'],i)
    assert balance.in_zone(q)
