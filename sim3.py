# 条件3: 先攻T2にメガガルーラexが技宣言(無色3)できる確率 / アカマツ不使用
# エネ供給は単線: 手張りT1(ガルーラへ直付け) + 手張りT2 + みどりのまいの草1枚をエネルギーつけかえでガルーラへ
# エネルギーを切って逃げる動きは不採用(例外: みどりのまい後のオーガポン自身の退避のみ可)
import random, sys
from sim import BASICS, ENER, pay_hyper, pick_start, CORE, hyper_ok, dance_ok, do_dance

ANY_EN = ('GRASS','PSY','WATER','FIGHT','LIGHT','PRISM')

def unmet(hand, st, hyper_avail, cyrano):
    best = None
    # ハイパーでポケモンを追加する線は「全員ハイパーNG」通算判定を通ったときのみ
    can_hyper = hyper_avail and hyper_ok(st['need'] + 1, st['nhyp'] + 1)
    targets = [None] + (['LATIAS','MIDORI'] if can_hyper else [])
    for t in targets:
        lat = st['latias'] or (t == 'LATIAS' and 'LATIAS' in st['avail']) or (cyrano and 'LATIAS' in st['avail'])
        midp = st['midori'] or ('MIDORI' in hand) or (t == 'MIDORI' and 'MIDORI' in st['avail']) \
               or (cyrano and 'MIDORI' in st['avail'])
        m = set()
        if not st['active'] and not ('IREKAE' in hand or lat): m.add('PROMOTE')
        if not any(c in ENER for c in hand): m.add('ATTACH')
        if 'TSUKEKAE' not in hand: m.add('MOVE')
        if st['grass'] < 1:
            # みどりのまいは手札の基本草エネを1枚消費する(2026-09-15 修正)
            if not midp: m.add('MIDORI_P')
            if 'GRASS' not in hand: m.add('GRASS')
            elif sum(1 for c in hand if c in ENER) < 2: m.add('ATTACH')
        if best is None or len(m) < len(best): best = m
    return best

FETCH = {'PROMOTE': ('IREKAE','LATIAS'), 'ATTACH': ANY_EN, 'MOVE': ('TSUKEKAE',),
         'GRASS': ('GRASS',), 'MIDORI_P': ('MIDORI',)}

def trial3(tmpl, rnd, stats, deal=None):
    if deal is not None:
        d = list(deal)
    else:
        d = tmpl[:]
        rnd.shuffle(d)
        while True:
            if any(c in BASICS for c in d[:7]): break
            rnd.shuffle(d)
    hand = list(d[:7]); deck = d[13:]
    avail = set(deck)
    def draw(n=1):
        for _ in range(n):
            if deck: hand.append(deck.pop(0))

    start = pick_start([c for c in hand if c in BASICS])
    hand.remove(start)
    draw(1)
    active = start; bench = []
    hyper = 1
    esc = {'GARURA': 3, 'LATIAS': 0, 'KAPU': 0}.get(start, 1)
    gar_in_play = (active == 'GARURA')
    grass = 0; dance_used = False

    # 「必要ポケモン」計上(判断2=案B: プランに寄与したポケモンは現物/スタートも数える)
    need = 0; nhyp = 0
    gar_counted = lat_counted = mid_counted = False
    if gar_in_play:
        need += 1; gar_counted = True

    # ---- T1: ガルーラを場に(できればバトル場へ / 無償退避のみ) ----
    if not gar_in_play:
        gsrc = None
        if 'GARURA' in hand: gsrc = 'hand'
        elif 'MEGASIG' in hand and 'GARURA' in avail: gsrc = 'mega'
        elif hyper and 'HYPER' in hand and 'GARURA' in avail and len(hand) >= 3: gsrc = 'hyper'
        if gsrc:
            route = None
            if esc == 0: route = 'free'
            elif 'LATIAS' in hand: route = 'latias'
            elif start == 'MIDORI' and dance_ok(hand): route = 'midori_self'
            elif 'IREKAE' in hand: route = 'irekae'
            elif gsrc != 'hyper' and hyper and 'HYPER' in hand and 'LATIAS' in avail and len(hand) >= 3: route = 'hyper_latias'
            if gsrc == 'hand': hand.remove('GARURA')
            elif gsrc == 'mega': hand.remove('MEGASIG')
            else:
                prot = {'latias': {'LATIAS'}, 'irekae': {'IREKAE'}}.get(route, set())
                hand.remove('HYPER'); pay_hyper(hand, CORE | prot, keep_en=1); hyper = 0
            gar_in_play = True
            need += 1; gar_counted = True
            if gsrc == 'hyper': nhyp += 1
            ok = True
            if route == 'free':
                need += 1                      # 逃げ0のスタート(ラティアス/コケコ)が前出しに寄与
                if start == 'LATIAS': lat_counted = True
            elif route == 'latias':
                if 'LATIAS' in hand:
                    hand.remove('LATIAS'); bench.append('LATIAS')
                    need += 1; lat_counted = True
                else: ok = False
            elif route == 'midori_self':
                if do_dance(hand):                  # 手札の草を貼って退避コストで捨てる(例外許可)
                    dance_used = True; draw(1)
                    bench.append('MIDORI')
                    need += 1; mid_counted = True
                else: ok = False
            elif route == 'irekae':
                if 'IREKAE' in hand: hand.remove('IREKAE')
                else: ok = False
            elif route == 'hyper_latias':
                if 'HYPER' in hand and len(hand) >= 3:
                    hand.remove('HYPER'); pay_hyper(hand, {'GARURA'}, keep_en=1); hyper = 0; bench.append('LATIAS')
                    need += 1; nhyp += 1; lat_counted = True
                else: ok = False
            elif route is None:
                ok = False
            if ok and route:
                if start not in bench: bench.append(start)
                active = 'GARURA'
            else:
                bench.append('GARURA')
    if not gar_in_play:
        stats['no_garura'] += 1
        return False

    # ---- T1 展開 ----
    if active == 'GARURA': draw(2)                  # おつかいダッシュ
    if 'MIDORI' not in bench and active != 'MIDORI' and 'MIDORI' in hand:
        hand.remove('MIDORI'); bench.append('MIDORI')
    midori_in_play = ('MIDORI' in bench) or (active == 'MIDORI')
    mid_by_hyper = False
    if not midori_in_play and hyper and 'HYPER' in hand and 'MIDORI' in avail and len(hand) >= 3:
        hand.remove('HYPER'); pay_hyper(hand, CORE, keep_en=1); hyper = 0
        bench.append('MIDORI'); midori_in_play = True; mid_by_hyper = True
    if midori_in_play and not dance_used and dance_ok(hand):
        dance_used = True; do_dance(hand); grass += 1; draw(1)
        if not mid_counted:
            need += 1; mid_counted = True
            if mid_by_hyper: nhyp += 1
    if 'LATIAS' in hand:
        hand.remove('LATIAS'); bench.append('LATIAS')
        if not lat_counted: need += 1; lat_counted = True
    if hyper and 'HYPER' in hand and 'LATIAS' not in bench and 'IREKAE' not in hand \
       and active != 'GARURA' and 'LATIAS' in avail and len(hand) >= 3:
        hand.remove('HYPER'); pay_hyper(hand, CORE, keep_en=1); hyper = 0; bench.append('LATIAS')
        if not lat_counted: need += 1; nhyp += 1; lat_counted = True
    # T1 手張り(ガルーラへ直付け。無ければ達成不能)
    e_gar = 0
    for c in list(hand):
        if c in ENER:
            hand.remove(c); e_gar = 1; break
    if e_gar == 0:
        stats['no_t1_energy'] += 1
        return False

    # ---- T2 ----
    draw(1)
    st = {'active': active == 'GARURA', 'latias': 'LATIAS' in bench,
          'midori': midori_in_play, 'grass': grass, 'avail': set(deck),
          'need': need, 'nhyp': nhyp}
    hyper_t2 = 1 if 'HYPER' in hand else 0

    def sup_ok(s):
        """サポート s を撃つコスト: (hyper使用数, ポケモン新規計上) or None"""
        if s in hand: return (0, 0)
        if 'NYASU' in hand and s in st['avail']: return (0, 1)
        if hyper_t2 and 'NYASU' in st['avail'] and s in st['avail'] and len(hand) >= 4 \
           and hyper_ok(st['need'] + 1, st['nhyp'] + 1): return (1, 1)
        return None

    # (1) 暗号マニアの解読を先に撃つプラン(山上に2枚積んでドローで引き込む)
    hc = sup_ok('ANGO')
    if hc is not None:
        sta = dict(st, need=st['need'] + hc[1], nhyp=st['nhyp'] + hc[0])
        u0 = unmet(hand, sta, max(hyper_t2 - hc[0], 0), False)
        if u0:
            draws = (2 if (st['active'] or 'IREKAE' in hand or st['latias']) else 0) + (1 if st['midori'] else 0)
            if len(u0) <= min(2, draws) and all(any(x in st['avail'] for x in FETCH[p]) for p in u0):
                return True
    # (2) ドロー(ダッシュ/みどりのまい)を先に回してから判断
    # ガルーラがベンチでも、この番に前出しできるならダッシュは使える
    if not st['active'] and ('IREKAE' in hand or st['latias']):
        if not st['latias'] and 'IREKAE' in hand: hand.remove('IREKAE')
        st['active'] = True
    if st['active']: draw(2)
    if st['midori'] and dance_ok(hand):   # T1でダンス済みでも次の番は再度使える
        do_dance(hand); st['grass'] += 1; draw(1)
    st['avail'] = set(deck)
    hyper_t2 = 1 if 'HYPER' in hand else 0

    u = unmet(hand, st, hyper_t2, False)
    if not u: return True
    hc = sup_ok('CYRANO')
    if hc is not None:
        stc = dict(st, need=st['need'] + hc[1], nhyp=st['nhyp'] + hc[0])
        if not unmet(hand, stc, hyper_t2 - hc[0], True): return True
    hc = sup_ok('ANGO')
    if hc is not None:
        draws = 0  # ダッシュ・みどりのまいは使用済み
        if len(u) <= draws: return True
    hc = sup_ok('LILLIE')
    if hc is not None:
        if 'LILLIE' in hand: hand.remove('LILLIE')
        # 手札で埋まる分は先に処理(手張り・つけかえ・前出し)→残りをリーリエで掘る
        st2 = dict(st)
        st2['need'] = st['need'] + hc[1]; st2['nhyp'] = st['nhyp'] + hc[0]
        if 'PROMOTE' not in u: st2['active'] = True
        if 'GRASS' not in u and 'MIDORI_P' not in u: st2['grass'] = max(st2['grass'], 1)
        req = set(u)
        # 草が無い状態ではリーリエ前につけかえを使えない(草が出てから移動するため)
        if 'GRASS' in u and 'MOVE' not in u: req.add('MOVE')
        deck.extend(hand); hand.clear(); rnd.shuffle(deck); draw(8)
        st2['avail'] = set(deck)
        h2 = 0 if hc[0] else (1 if 'HYPER' in hand else 0)  # ニャース確保にハイパーを使った場合は残らない
        u2 = unmet(hand, st2, h2, False)
        if not (req & u2): return True
    for p in u: stats['miss_' + p] += 1
    return False

def run3(counts, trials, seed=777):
    tmpl = []
    for k, v in counts.items(): tmpl += [k] * v
    assert len(tmpl) == 60
    rnd = random.Random(seed)
    from collections import Counter
    stats = Counter()
    n = 0
    for _ in range(trials):
        if trial3(tmpl, rnd, stats): n += 1
    return n / trials * 100, stats, trials

if __name__ == '__main__':
    from decks import OLD, CUR
    T = int(sys.argv[1]) if len(sys.argv) > 1 else 300000
    for name, cfg in (('現行(2026-09-12更新後)', CUR), ('旧リスト', OLD)):
        p, stats, T2 = run3(cfg, T)
        print(f'{name}: 条件3 = {p:.1f}%')
        tot = sum(stats.values())
        if tot:
            det = ' / '.join(f'{k}:{v/T2*100:.1f}%' for k, v in stats.most_common())
            print('   未達要因(重複あり・試行比): ' + det)
