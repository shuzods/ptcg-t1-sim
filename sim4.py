# 条件4: 先攻T2にメガガルーラexが技宣言(無色3) / 先1手張り + 先2アカマツ
# エネ供給: 先1手張り(ガルーラ直付け固定) + アカマツの直付与1 + アカマツで手札に来たエネの手張り1 = 3
# 退避でエネを切る動きは不採用(例外: みどりのまい後のオーガポン自身のみ)
# アカマツを撃つ番は他サポート併用不可(リーリエ等のフォールバックなし)
import random, sys
from collections import Counter
from sim import BASICS, ENER, pay_hyper, pick_start, CORE, hyper_ok, dance_ok, do_dance

BASIC_EN = ('GRASS', 'PSY', 'WATER', 'FIGHT', 'LIGHT')   # プリズムはアカマツ対象外

def trial4(tmpl, rnd, stats, deal=None):
    if deal is not None:
        d = list(deal)
    else:
        d = tmpl[:]
        rnd.shuffle(d)
        while not any(c in BASICS for c in d[:7]):
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
    dance_used = False

    # 「必要ポケモン」計上(判断2=案B: プランに寄与したポケモンは現物/スタートも数える)
    need = 0; nhyp = 0
    lat_counted = nya_counted = False
    if gar_in_play: need += 1

    # ---- T1: ガルーラを場に(バトル場化は無償退避のみ) ----
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
            need += 1
            if gsrc == 'hyper': nhyp += 1
            ok = bool(route)
            if route == 'free':
                need += 1                       # 逃げ0のスタート(ラティアス/コケコ)が前出しに寄与
                if start == 'LATIAS': lat_counted = True
            elif route == 'latias':
                if 'LATIAS' in hand:
                    hand.remove('LATIAS'); bench.append('LATIAS')
                    need += 1; lat_counted = True
                else: ok = False
            elif route == 'midori_self':
                if do_dance(hand):
                    dance_used = True; draw(1); bench.append('MIDORI')
                    need += 1                   # オーガポン自身の草退避に寄与
                else: ok = False
            elif route == 'irekae':
                if 'IREKAE' in hand: hand.remove('IREKAE')
                else: ok = False
            elif route == 'hyper_latias':
                if 'HYPER' in hand and len(hand) >= 3:
                    hand.remove('HYPER'); pay_hyper(hand, {'GARURA'}, keep_en=1); hyper = 0; bench.append('LATIAS')
                    need += 1; nhyp += 1; lat_counted = True
                else: ok = False
            if ok:
                if start not in bench: bench.append(start)
                active = 'GARURA'
            else:
                bench.append('GARURA')
    if not gar_in_play:
        stats['no_garura'] += 1
        return False

    # ---- T1 展開 ----
    if active == 'GARURA': draw(2)                       # おつかいダッシュ
    if 'MIDORI' not in bench and active != 'MIDORI' and 'MIDORI' in hand:
        hand.remove('MIDORI'); bench.append('MIDORI')
    midori_in_play = ('MIDORI' in bench) or (active == 'MIDORI')
    if midori_in_play and not dance_used and dance_ok(hand):
        dance_used = True; do_dance(hand); draw(1)       # 草は本条件では不要・ドローのみ利用
    if 'LATIAS' in hand:
        hand.remove('LATIAS'); bench.append('LATIAS')
        if not lat_counted: need += 1; lat_counted = True
    # T1に余ったハイパー: ガルーラがベンチ止まりなら前出し用ラティアス、次にアカマツ用ニャース
    if hyper and 'HYPER' in hand and len(hand) >= 3:
        if active != 'GARURA' and 'LATIAS' not in bench and 'IREKAE' not in hand and 'LATIAS' in avail:
            hand.remove('HYPER'); pay_hyper(hand, CORE, keep_en=1); hyper = 0; bench.append('LATIAS')
            if not lat_counted: need += 1; nhyp += 1; lat_counted = True
        elif 'AKAMATSU' not in hand and 'NYASU' not in hand and 'NYASU' in avail and 'AKAMATSU' in avail:
            hand.remove('HYPER'); pay_hyper(hand, CORE, keep_en=1); hyper = 0
            bench.append('NYASU'); hand.append('AKAMATSU')          # おくのてキャッチで確保(保持)
            need += 1; nhyp += 1; nya_counted = True
    # ニャース現物があり、アカマツが手札に無ければT1に出して確保しておく
    if 'AKAMATSU' not in hand and 'NYASU' in hand and 'AKAMATSU' in set(deck):
        hand.remove('NYASU'); bench.append('NYASU')
        deck.remove('AKAMATSU'); hand.append('AKAMATSU')
        need += 1; nya_counted = True
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
    if active != 'GARURA' and ('IREKAE' in hand or 'LATIAS' in bench):
        if 'LATIAS' not in bench: hand.remove('IREKAE')
        active = 'GARURA'
    if active == 'GARURA': draw(2)
    if midori_in_play and dance_ok(hand, keep_attach=False):   # T2は手張りをアカマツ由来で賄うため草を使い切ってよい
        do_dance(hand); draw(1)
    avail2 = set(deck)
    hyper_t2 = 1 if ('HYPER' in hand and len(hand) >= 3) else 0

    miss = set()
    # アカマツの確保: (hyper使用数, ポケモン新規計上)
    ak_opts = []
    if 'AKAMATSU' in hand: ak_opts.append((0, 0))
    if 'NYASU' in hand and 'AKAMATSU' in avail2: ak_opts.append((0, 1))
    if hyper_t2 and 'NYASU' in avail2 and 'AKAMATSU' in avail2: ak_opts.append((1, 1))
    # 前出し(無償のみ): (hyper使用数, ポケモン新規計上)
    pr_opts = []
    if active == 'GARURA' or 'IREKAE' in hand or 'LATIAS' in bench: pr_opts.append((0, 0))
    if hyper_t2 and 'LATIAS' in avail2: pr_opts.append((1, 0 if lat_counted else 1))
    if not ak_opts: miss.add('AKAMATSU')
    if not pr_opts: miss.add('PROMOTE')
    # アカマツの「異なる2色の基本エネ」が山札に残っているか
    if len({c for c in avail2 if c in BASIC_EN}) < 2: miss.add('AKAMATSU_TYPES')
    if not miss:
        combo = False
        for ah, ap in ak_opts:
            for ph, pp in pr_opts:
                uh = ah + ph
                if uh > hyper_t2: continue
                if len(hand) < 2 * uh + 1: continue
                if not hyper_ok(need + ap + pp, nhyp + uh): continue
                combo = True; break
            if combo: break
        if not combo: miss.add('HYPER_CONFLICT')
    if miss:
        for p in miss: stats['miss_' + p] += 1
        return False
    return True

def run4(counts, trials, seed=555):
    tmpl = []
    for k, v in counts.items(): tmpl += [k] * v
    assert len(tmpl) == 60
    rnd = random.Random(seed)
    stats = Counter(); n = 0
    for _ in range(trials):
        if trial4(tmpl, rnd, stats): n += 1
    return n / trials * 100, stats, trials

if __name__ == '__main__':
    from decks import OLD, CUR
    T = int(sys.argv[1]) if len(sys.argv) > 1 else 300000
    for name, cfg in (('現行(2026-09-12更新後)', CUR), ('旧リスト', OLD)):
        p, st, T2 = run4(cfg, T)
        print(f'{name}: 条件4 = {p:.1f}%')
        print('   未達要因(重複あり・試行比): ' + ' / '.join(f'{k}:{v/T2*100:.1f}%' for k, v in st.most_common()))
