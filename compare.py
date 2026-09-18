# 構成比較ドライバ: 任意の構成について 条件1〜6 + 先/後の「いずれか達成(現実的選択)」を一括算出
import sys, random
from collections import Counter
import sim, sim3, sim4, sim_back
from sim import BASICS


def front_pick(view8, c1, c2, c3, c4):
    """先攻の「いずれか達成(現実的選択)」のプラン選択(2026-09-18 改訂)。

    旧実装は `('FIRO' in view8) or ('CYRANO' in view8)` の1行で、先1の8枚だけを見て
    条件2かガルーラの線かを決め打ちしていた。しかし条件2・3・4はいずれも
    「先1にガルーラをバトル場+手張り」から始まるため、多くの配りでは先1の動きが共通で、
    どの線で殴るかは先2に決められる。30万試行で完全情報上限 67.4% に対し旧実装は 59.8% で、
    7.6pt を作り過ぎていた(内訳 α3.5 / β4.0。詳細は SENSITIVITY.md)。

    view8 = 初手7枚 + 先1のターン頭ドロー1枚(先1に見えている情報のみ)。
    c1 は先1にガルーラがバトル場に立ち、かつ手張りを退避に使わずに済んだか
    (= 先1の動きが両線で共通になり、選択を先2へ持ち越せるか)の判定に使う。

    「8枚にエネが無ければガルーラの線は成立し得ない」という規則も検討したが**不採用**。
    先1のおつかいダッシュ2ドローは手張りより前に走るため、8枚にエネが無くても
    ダッシュで引ける。実測で 1.27pt の勝ちを捨てていた(2026-09-18 自己レビューで検出)。"""
    gar = c3 or c4
    if c1:
        return c2 or gar   # 規則1: 先1の動きが共通→選択を先2に持ち越す
    # 規則2: 先1で不可逆な分岐が強制される→8枚の情報で選ぶ
    return c2 if (('FIRO' in view8) or ('CYRANO' in view8)) else gar
from decks import CUR, MID, OLD
from sim3 import trial3
from sim4 import trial4
from sim_back import trial_back


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
    assert len(t) == 60, ('デッキ枚数が60ではありません', len(t))
    return t


def run_front(counts, trials, seed=31415):
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
        c['front_any'] += front_pick(view8, c1, c2, c3, c4)
    return {k: c[k] / trials * 100 for k in ('c1', 'c2', 'c3', 'c4', 'front_any')}


def run_back_all(counts, trials, seed=9001):
    tmpl = tmpl_of(counts)
    rnd = random.Random(seed)
    st = Counter(); c = Counter()
    for _ in range(trials):
        a, b = trial_back(tmpl, rnd, st)
        c['c5'] += a; c['c6'] += b; c['back_any'] += (a or b)
    return {k: c[k] / trials * 100 for k in ('c5', 'c6', 'back_any')}


def run_all(counts, trials, fseed=31415, bseed=9001):
    r = run_front(counts, trials, fseed)
    r.update(run_back_all(counts, trials, bseed))
    return r


KEYS = [('c1', '条件1 先1ガルーラ着地'),
        ('c2', '条件2 先2ファイアロー技宣言'),
        ('c3', '条件3 先2ガルーラ・アカマツ不使用'),
        ('c4', '条件4 先2ガルーラ・アカマツ使用'),
        ('front_any', 'いずれか達成(条件2/3/4・現実的選択)'),
        ('c5', '条件5 後1ファイアロー技宣言'),
        ('c6', '条件6 後1ガルーラ・アカマツ使用'),
        ('back_any', 'いずれか達成(条件5/6)')]


def table(results, trials):
    """results: [(ラベル, dict), ...] 先頭を基準にして差分を出す"""
    names = [n for n, _ in results]
    base = results[0][1]
    w = max(len(k[1]) for k in KEYS)
    head = '| ' + '条件'.ljust(w) + ' | ' + ' | '.join(n.ljust(10) for n in names) + ' |'
    print(f'--- {trials}試行 ---')
    print(head)
    for k, label in KEYS:
        cells = []
        for i, (n, r) in enumerate(results):
            if i == 0:
                cells.append(f'{r[k]:.1f}%'.ljust(10))
            else:
                cells.append(f'{r[k]:.1f}% ({r[k]-base[k]:+.1f})'.ljust(10))
        print('| ' + label.ljust(w) + ' | ' + ' | '.join(cells) + ' |')


if __name__ == '__main__':
    T = int(sys.argv[1]) if len(sys.argv) > 1 else 300000
    res = [('現行', run_all(CUR, T))]
    table(res, T)
