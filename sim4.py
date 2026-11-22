# 条件4: 先攻T2にメガガルーラexが技宣言(無色3) / 先1手張り + 先2アカマツ
# エネ供給: 先1手張り(ガルーラ直付け固定) + アカマツの直付与1 + アカマツで手札に来たエネの手張り1 = 3
# 退避でエネを切る動きは不採用(例外: みどりのまい後のオーガポン自身のみ)
# アカマツを撃つ番は他サポート併用不可(リーリエ等のフォールバックなし)
import random, sys
from collections import Counter
import sim as _sim
from sim import BASICS, ENER, pay_hyper, pick_start, CORE, hyper_ok, dance_ok, do_dance, dig_for_garura, hand_need

BASIC_EN = ('GRASS', 'PSY', 'WATER', 'FIGHT', 'LIGHT')   # プリズムはアカマツ対象外

def _trial4(tmpl, rnd, stats, deal=None, t1_cap=None):
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
    hyper = _sim.HYPER_T1_MAX if t1_cap is None else t1_cap
    esc = {'GARURA': 3, 'LATIAS': 0, 'KAPU': 0}.get(start, 1)
    gar_in_play = (active == 'GARURA')
    dance_used = False

    # 「必要ポケモン」計上(判断2=案B: プランに寄与したポケモンは現物/スタートも数える)
    need = 0; nhyp = 0
    lat_counted = nya_counted = False
    if gar_in_play: need += 1

    # ---- T1: ガルーラを場に(バトル場化は無償退避のみ) ----
    dug_act = False; dug_nb = 0
    if not gar_in_play:
        dug_act, dug_nb = dig_for_garura(hand, draw, active, bench, avail, hyper)
        if dug_nb:
            dance_used = True
        gsrc = None
        if 'GARURA' in hand: gsrc = 'hand'
        elif 'MEGASIG' in hand and 'GARURA' in avail: gsrc = 'mega'
        elif hyper and 'HYPER' in hand and 'GARURA' in avail and len(hand) >= 3: gsrc = 'hyper'
        if gsrc:
            def _route():
                if esc == 0: return 'free'
                if 'LATIAS' in hand: return 'latias'
                if start == 'MIDORI' and (dug_act or dance_ok(hand)): return 'midori_self'
                if 'IREKAE' in hand: return 'irekae'
                if hyper >= (2 if gsrc == 'hyper' else 1) and hand.count('HYPER') >= (2 if gsrc == 'hyper' else 1) \
                        and 'LATIAS' in avail and len(hand) >= (6 if gsrc == 'hyper' else 3): return 'hyper_latias'
                return None
            route = _route()
            # 2026-11-22: 前出し手段が無ければ、手札のオーガポンをベンチに出してみどりのまいで掘る。
            # この条件は先1の手張りが必須なので、手張り用のエネを1枚残せるとき(dance_ok)だけ掘る
            while _sim.PROMOTE_DIG and route is None and 'MIDORI' in hand and dance_ok(hand) \
                    and (gsrc != 'hyper' or len(hand) >= 5):
                hand.remove('MIDORI'); bench.append('MIDORI'); do_dance(hand); draw(1)
                dance_used = True
                route = _route()
            if gsrc == 'hand': hand.remove('GARURA')
            elif gsrc == 'mega': hand.remove('MEGASIG')
            else:
                prot = {'latias': {'LATIAS'}, 'irekae': {'IREKAE'}}.get(route, set())
                hand.remove('HYPER'); pay_hyper(hand, CORE | prot, keep_en=1); hyper -= 1
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
                if dug_act or do_dance(hand):
                    if not dug_act: draw(1)
                    dance_used = True; bench.append('MIDORI')
                    need += 1                   # オーガポン自身の草退避に寄与
                else: ok = False
            elif route == 'irekae':
                if 'IREKAE' in hand: hand.remove('IREKAE')
                else: ok = False
            elif route == 'hyper_latias':
                if 'HYPER' in hand and len(hand) >= 3:
                    hand.remove('HYPER'); pay_hyper(hand, {'GARURA'}, keep_en=1); hyper -= 1; bench.append('LATIAS')
                    need += 1; nhyp += 1; lat_counted = True
                else: ok = False
            if dug_act:
                dance_used = True                    # 掘ったバトル場のオーガポンは、このターンもう撃てない
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
            hand.remove('HYPER'); pay_hyper(hand, CORE, keep_en=1); hyper -= 1; bench.append('LATIAS')
            if not lat_counted: need += 1; nhyp += 1; lat_counted = True
            did_latias_hyper = True
        else:
            did_latias_hyper = False
        # 2026-11-22: ラティアスをハイパーで補った後にもう1枚使えるなら、ニャース確保の線も続けて評価する
        # (旧実装の elif と等価: 旧設定では hyper が 0 になるため2つ目は実行されない)
        if (not did_latias_hyper or (hyper and 'HYPER' in hand and len(hand) >= 3)) \
                and 'AKAMATSU' not in hand and 'NYASU' not in hand and 'NYASU' in avail and 'AKAMATSU' in avail:
            hand.remove('HYPER'); pay_hyper(hand, CORE, keep_en=1); hyper -= 1
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
    hyper_t2 = min(_sim.HYPER_T2_MAX, hand.count('HYPER')) if len(hand) >= 3 else 0

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
                if len(hand) < hand_need(uh): continue
                if not hyper_ok(need + ap + pp, nhyp + uh): continue
                combo = True; break
            if combo: break
        if not combo: miss.add('HYPER_CONFLICT')
    if miss:
        for p in miss: stats['miss_' + p] += 1
        return False
    return True

def trial4(tmpl, rnd, stats, deal=None):
    """条件4。2026-11-22: 先攻T1でハイパー2枚使う新しい線で未達のとき、旧来(T1は1枚まで)の線でも
    評価して、どちらかで成立すれば達成とする(規約を緩めて値が下がらないための最善手評価)。"""
    if deal is None:
        d = tmpl[:]
        rnd.shuffle(d)
        while not any(c in BASICS for c in d[:7]):
            rnd.shuffle(d)
    else:
        d = list(deal)
    tmp = Counter()
    if _trial4(tmpl, rnd, tmp, d): return True
    # リーリエ採用デッキでは、引き直しのランダム性により2つの線のORが二重引き直しになり過大評価となるため、再評価は行わない(リーリエ0枚のデッキでは試行が配りだけで決まるので問題ない)。
    if _sim.HYPER_T1_MAX > 1 and 'LILLIE' not in tmpl:
        if _trial4(tmpl, random.Random(','.join(d) + '|cap1'), Counter(), d, t1_cap=1): return True
    stats.update(tmp)
    return False

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
