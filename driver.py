# v2改修の再算出ドライバ: 条件1〜4 + 和集合、制約あり/なしの差分、構造テスト
import sys, random
from collections import Counter
import sim, sim3, sim4
from sim import BASICS
from decks import CUR, OLD
from sim3 import trial3
from sim4 import trial4

T = int(sys.argv[1]) if len(sys.argv) > 1 else 300000

def variant(base, **kw):
    """カードを抜いた分を無関係なトレーナーズ(FILLER)で置換し60枚を維持"""
    v = dict(base); removed = 0
    for k, n in kw.items():
        removed += v.get(k, 0) - n
        v[k] = n
    if removed: v['FILLER'] = v.get('FILLER', 0) + removed
    return {k: n for k, n in v.items() if n > 0}

def tmpl_of(counts):
    t = []
    for k, v in counts.items(): t += [k] * v
    assert len(t) == 60, len(t)
    return t

def run_all(counts, trials, seed=31415):
    """同一の配りに4条件を当てる(和集合は同一乱数由来)"""
    tmpl = tmpl_of(counts)
    rnd = random.Random(seed)
    st = Counter(); c = Counter()
    for _ in range(trials):
        d = tmpl[:]
        rnd.shuffle(d)
        while not any(x in BASICS for x in d[:7]):
            rnd.shuffle(d)
        view8 = d[:7] + [d[13]]
        c1, z, ok2 = sim.trial(tmpl, rnd, deal=d)
        c2 = bool(z and ok2)
        c3 = trial3(tmpl, rnd, st, deal=d)
        c4 = trial4(tmpl, rnd, st, deal=d)
        c['c1'] += c1; c['c2'] += c2; c['c3'] += c3; c['c4'] += c4
        pick2 = ('FIRO' in view8) or ('CYRANO' in view8)
        c['heur'] += (c2 if pick2 else (c3 or c4))
    return {k: c[k] / trials * 100 for k in ('c1', 'c2', 'c3', 'c4', 'heur')}

def set_rule(on):
    f = sim.hyper_ok if on else (lambda need, nhyp: True)
    sim.hyper_ok = f if on else f
    sim3.hyper_ok = f
    sim4.hyper_ok = f

REAL = sim.hyper_ok
OFF = lambda need, nhyp: True

if __name__ == '__main__':
    print(f'=== 再算出 ({T}試行) ===')
    for label, cfg in (('現行', CUR), ('旧リスト', OLD)):
        sim.hyper_ok = sim3.hyper_ok = sim4.hyper_ok = REAL
        new = run_all(cfg, T)
        sim.hyper_ok = sim3.hyper_ok = sim4.hyper_ok = OFF
        old = run_all(cfg, T)
        print(f'--- {label} ---')
        for k, nm in (('c1','条件1'),('c2','条件2'),('c3','条件3'),('c4','条件4'),('heur','いずれか(2/3/4)')):
            print(f'  {nm}: v2={new[k]:.1f}%  v1相当(制約なし)={old[k]:.1f}%  差={new[k]-old[k]:+.1f}pt')

    sim.hyper_ok = sim3.hyper_ok = sim4.hyper_ok = REAL
    print('\n=== 構造テスト(必須ピースを0枚: 0.0%になるか) ===')
    tests = [
        ('GARURA=0', variant(CUR, GARURA=0), ('c1','c2','c3','c4')),
        ('FIRO=0',   variant(CUR, FIRO=0),   ('c2',)),
        ('TSUKEKAE=0', variant(CUR, TSUKEKAE=0), ('c3',)),
        ('MIDORI=0', variant(CUR, MIDORI=0), ('c3',)),
        ('AKAMATSU=0', variant(CUR, AKAMATSU=0), ('c4',)),
        ('エネ全0', variant(CUR, GRASS=0, PSY=0, WATER=0, FIGHT=0, LIGHT=0, PRISM=0), ('c2','c3','c4')),
    ]
    for nm, cfg, keys in tests:
        r = run_all(cfg, 30000, seed=4242)
        print(f'  {nm}: ' + ' '.join(f'{k}={r[k]:.1f}%' for k in keys))
