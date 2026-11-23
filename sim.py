import random, sys

BASICS = {'GARURA','PIPPI','NYASU','LATIAS','KICHI','IDO','KAPU','NAGE','PAO','MIDORI'}
ENER   = {'GRASS','PSY','WATER','FIGHT','LIGHT','PRISM','TELEPATH'}
BASIC_EN = ('GRASS','PSY','WATER','FIGHT','LIGHT')   # プリズムはアカマツ対象外
SUPS   = {'AKAMATSU','BOSS','LILLIE','CYRANO','JUDGE','ANGO'}
JUNK   = ['FILLER','CAVERN','BOSS','JUDGE','ANGO','STAMP','TANKA','PIPPI','NAGE','PAO','KICHI','IDO','PSY','WATER','FIGHT','LIGHT']

OTHER_ORDER = ['PIPPI','PAO','NAGE','KICHI','IDO','NYASU']
CORE = {'GARURA','FIRO','LATIAS','MIDORI','IREKAE','TSUKEKAE','AKAMATSU','CYRANO','LILLIE',
        'NYASU','MEGASIG','HYPER','GRASS','PSY','WATER','FIGHT','LIGHT','PRISM','TELEPATH'}

# ── 2026-11-23: テレパス超エネルギー(megagarura-b で採用) ─────────────────────
# 手札から超ポケモン(ピッピ/ラティアスex)に手張りしたとき、山札から超ポケモンを2体までベンチに出す。
# T1の前出し線: ピッピ(バトル場 or 手札からベンチ)にテレパスを手張り → 山札のラティアスexをベンチ
# → スカイラインで逃げ0 → ガルーラを無償で前に出す。手張りはテレパスで使い切る(退避コストではない)。
# 手札にテレパスが無いデッキでは一切発動しない(megagarura の値は不変)。False で無効。
TELEPATH_ROUTE = True
PSY_POKE = ('PIPPI', 'LATIAS')
# 2026-11-23: スタートのときだけテレパスの手張り先にするポケモン(デッキ側で設定。例: {'KASHIRA'})。
# ユーザー指定: カシラにテレパスを貼るのは「カシラスタート+ガルーラをハイパーを使わずに確保した(=ターン最初のドローで引いた)」場合のみ
TELEPATH_START_ONLY = set()
T1_SNAP = None   # 条件Bの判定用: T1の前出し後(ダッシュ後)の状態を書き出す先(dict を入れると記録)

# 逃げコスト表(先攻・後攻で共用。未登録のたねは1として扱う)
ESC = {'GARURA': 3, 'LATIAS': 0, 'KAPU': 0, 'FIRO': 0}


def register_cards(spec):
    """カード属性をエンジン外(decks.py の CARDS)から取り込む拡張点。

    エンジンを編集せずにカードを追加するための仕組み。spec は
      {カード名: dict(basic=bool, esc=int, start='last'|'first'|int, junk_after=カード名)}
    basic      : たねポケモンとして扱う
    esc        : 逃げコスト(省略時は1)
    start      : pick_start の優先順位。'last'=最低、'first'=OTHER_ORDER の先頭、int=挿入位置
    junk_after : ハイパーボールの捨て優先度。指定カードの直後に差し込む(省略時は捨てない札扱い)
    """
    for name, a in (spec or {}).items():
        if a.get('basic'):
            BASICS.add(name)
        if 'esc' in a:
            ESC[name] = a['esc']
        pos = a.get('start')
        if pos is not None and name not in OTHER_ORDER:
            if pos == 'last':
                OTHER_ORDER.append(name)
            elif pos == 'first':
                OTHER_ORDER.insert(0, name)
            else:
                OTHER_ORDER.insert(int(pos), name)
        after = a.get('junk_after')
        if after is not None and name not in JUNK:
            JUNK.insert(JUNK.index(after) + 1, name)
            DISCARD_ORDER.insert(DISCARD_ORDER.index(after) + 1, name)


try:
    from decks import CARDS as _CARDS
except Exception:
    _CARDS = {}


# ── ハイパーボールの先攻規約(2026-11-22 ユーザー確定で緩和) ─────────────
# HYPER_T1_MAX / HYPER_T2_MAX : 先攻T1・T2それぞれで1ターンに使えるハイパーボールの枚数上限
#   旧規約=1(T1で1回・T2で1回)。新規約=2。
# HYPER_RULE : 'all_ng' = 旧「全員ハイパーNG」(必要ポケモンが2体以上のとき全員をハイパーで賄うのは不可)
#              'cover2' = 新「ハイパーで補うポケモンは2体まで」(3体以上は不可。通算判定)
# 旧規約に戻すと旧エンジンと完全一致する(回帰確認用)。
HYPER_T1_MAX = 2
HYPER_T2_MAX = 2
HYPER_RULE = 'cover2'
HYPER_COVER_MAX = 2

def hyper_ok(need, nhyp):
    """共通規約「ハイパーで補うポケモンの数」の判定(先攻はT1+T2通算)。
    'cover2': ハイパーで補うポケモンは2体まで。
    'all_ng': 必要ポケモンが2体以上のとき、その全員をハイパーボールで賄う組み合わせは不可。
              必要ポケモンが1体だけの条件には適用しない(旧規約)。"""
    if HYPER_RULE == 'cover2':
        return nhyp <= HYPER_COVER_MAX
    return not (need >= 2 and nhyp >= need)

def hand_need(uh):
    """ハイパーを uh 回使うのに必要な手札枚数(ハイパー本体1+トラッシュ2 を uh 回)。
    uh<=1 は旧実装の式(2*uh+1)をそのまま踏襲し、2回以上は 3*uh とする。"""
    return 2 * uh + 1 if uh <= 1 else 3 * uh



# ── 2026-11-22: みどりのまいでガルーラの確保手段を掘る線 ─────────────────────
# A: みどりのまいで引いた1枚を、ガルーラの確保(現物/メガシグナル/ハイパー)に使う
# B: みどりのまいはオーガポン1体ごとに1ターン1回(ユーザー確認)。手札の2体目もベンチに出して掘る
# ガルーラの確保手段が手札に無いときだけ掘る(無ければ条件1〜4はいずれも未達なので、掘って損はない)。
# False で旧エンジンと完全一致(回帰確認用)。
DIG_DANCE = True
# 2026-11-22: ガルーラは確保できたが無償で前に出す手段が無いとき、手札のオーガポンをベンチに出して
# みどりのまいで前出し手段(ラティアスex/いれかえ/ハイパー/つけかえ)を掘る線。False で旧エンジンと完全一致
PROMOTE_DIG = True

def dig_for_garura(hand, draw, active, bench, avail, hyper_avail):
    """戻り値: (バトル場のオーガポンが掘ったか, ベンチに出して掘ったオーガポンの数)"""
    act = False; nb = 0
    if not DIG_DANCE: return act, nb
    def src():
        return ('GARURA' in hand or ('MEGASIG' in hand and 'GARURA' in avail)
                or (hyper_avail and 'HYPER' in hand and 'GARURA' in avail and len(hand) >= 3))
    while not src():
        if active == 'MIDORI' and not act and 'GRASS' in hand:
            hand.remove('GRASS'); draw(1); act = True; continue
        if 'MIDORI' in hand and 'GRASS' in hand:
            hand.remove('MIDORI'); bench.append('MIDORI'); hand.remove('GRASS'); draw(1); nb += 1; continue
        break
    return act, nb

def pick_start(basics):
    if 'GARURA' in basics: return 'GARURA'
    for c in ('LATIAS','KAPU'):
        if c in basics: return c
    if 'MIDORI' in basics: return 'MIDORI'
    for c in OTHER_ORDER:
        if c in basics: return c
    return basics[0]

DISCARD_ORDER = JUNK + ['PRISM','GRASS','TSUKEKAE','LILLIE','AKAMATSU','CYRANO',
                        'MEGASIG','NYASU','IREKAE','MIDORI','LATIAS','FIRO','HYPER','GARURA']

register_cards(_CARDS)


def dance_ok(hand, keep_attach=True):
    """みどりのまいを撃てるか。**手札に基本草エネルギーが必要**(2026-09-15 修正)。
    keep_attach=True のときは、その番の手張り用にエネを1枚残せる場合のみ撃つ(固定戦略・保守側)。"""
    if 'GRASS' not in hand:
        return False
    if not keep_attach:
        return True
    return sum(1 for c in hand if c in ENER) >= 2


def do_dance(hand):
    """みどりのまい実行: 手札から基本草エネを1枚消費し、オーガポン自身につける。
    草が無ければ何もせず False(ハイパーのトラッシュで落ちた稀ケース)。"""
    if 'GRASS' not in hand:
        return False
    hand.remove('GRASS')
    return True

def pay_hyper(hand, protect=(), keep_en=0):
    """discard 2 cards for hyper ball (junk first, protecting route-critical cards).

    keep_en: その番に手張りが必須の場面で手札に残すエネルギーの枚数(2026-09-18 追加)。
    DISCARD_ORDER は JUNK(超/水/闘/雷エネを含む)と 'GRASS' をリーリエ・アカマツ等より
    先に切るため、必須の手張り用エネを失う配りがあった(条件4が先1で脱落する例を実測)。
    手札のエネが keep_en 枚以下になった時点で、それらを保護対象に加える。"""
    if len(hand) < 2: return False
    for _ in range(2):
        prot = set(protect)
        if keep_en:
            en = [c for c in hand if c in ENER]
            if len(en) <= keep_en: prot |= set(en)
        tgt = None
        for j in DISCARD_ORDER:
            if j in hand and j not in prot: tgt = j; break
        if tgt is None and keep_en:                 # エネ保護を解いて再探索
            for j in DISCARD_ORDER:
                if j in hand and j not in protect: tgt = j; break
        if tgt is None:
            for j in DISCARD_ORDER:
                if j in hand: tgt = j; break
        if tgt is None: tgt = hand[-1]
        hand.remove(tgt)
    return True

def feas(hand, firo_in_play, e_firo, e_other, latias_in_play, avail,
         hyper_left, supporter, esc_active, sup_hyper_cost=0, sup_poke=0,
         need=0, nhyp=0):
    """先攻T2にファイアローがバトル場+エネ2枚になる手順が組めるか
    各選択肢は (ハイパー使用数, 新規に必要とするポケモン数) を持ち、
    通算で「全員ハイパー」になる組み合わせは hyper_ok で除外する"""
    tsuke = hand.count('TSUKEKAE')
    n_en = sum(1 for c in hand if c in ENER)
    big_hand = len(hand) >= 3
    # FIRO本体の入手手段: (hyperコスト, ポケモン新規計上, 必要サポート)
    firo_opts = []
    if firo_in_play: firo_opts.append((0, 0, None))        # T1で計上済み
    if 'FIRO' in hand: firo_opts.append((0, 1, None))
    if supporter == 'CYRANO' and 'FIRO' in avail: firo_opts.append((0, 1, 'CYRANO'))
    if 'FIRO' in avail and big_hand: firo_opts.append((1, 1, None))
    if not firo_opts: return False
    # 前出し手段: (hyperコスト, ポケモン新規計上, 必要サポート, 手張りを退避に消費するか)
    front_opts = []
    if hand.count('IREKAE') > 0: front_opts.append((0, 0, None, False))
    if latias_in_play: front_opts.append((0, 0, None, False))   # T1で計上済み
    if supporter == 'CYRANO' and 'LATIAS' in avail: front_opts.append((0, 1, 'CYRANO', False))
    if 'LATIAS' in avail and big_hand: front_opts.append((1, 1, None, False))
    if esc_active == 1: front_opts.append((0, 0, None, True))
    if not front_opts: return False
    # アカマツは「異なる2色の基本エネ」を山札から選ぶ(残っていなければ機能しない)
    aka = (supporter == 'AKAMATSU') and len({c for c in avail if c in BASIC_EN}) >= 2
    direct = 1 if aka else 0
    hand_en = n_en + (1 if aka else 0)
    for hf, pf, sf in firo_opts:
        for hr, pr, sr, paid_retreat in front_opts:
            uh = hf + hr + sup_hyper_cost
            if uh > hyper_left: continue
            if len(hand) < hand_need(uh): continue          # ハイパーのトラッシュコスト
            if sf and sf != supporter: continue
            if sr and sr != supporter: continue
            if not hyper_ok(need + pf + pr + sup_poke, nhyp + uh): continue
            if paid_retreat:
                if hand_en < 1: continue
                attach = 0
            else:
                attach = 1 if hand_en >= 1 else 0
            if e_firo + direct + attach + min(tsuke, e_other) >= 2:
                return True
    return False

def _trial(deck_template, rnd, deal=None, stats=None, no_paid=False, t1_cap=None, no_promote_dig=False):
    if deal is not None:
        d = list(deal)
    else:
        d = deck_template[:]
        rnd.shuffle(d)
        while True:
            hand = d[:7]
            if any(c in BASICS for c in hand): break
            rnd.shuffle(d)
    hand = list(d[:7]); prizes = d[7:13]; deck = d[13:]
    avail = set(deck)

    def draw(n=1):
        for _ in range(n):
            if deck: hand.append(deck.pop(0))

    start = pick_start([c for c in hand if c in BASICS])
    hand.remove(start)
    draw(1)   # ターン頭ドロー

    active = start
    bench = []
    e_firo = 0; e_other = 0
    hyper_t1 = HYPER_T1_MAX if t1_cap is None else t1_cap   # 先攻T1のハイパー使用可能枚数(2026-11-22: 1→2。t1_cap で上書き)
    paid = False
    midori_used = False
    esc = ESC.get(start, 1)

    # 「必要ポケモン」計上(判断2=案B: プランに寄与したポケモンは現物/スタートも数える)
    need = 0; nhyp = 0
    gar_counted = lat_counted = mid_counted = False
    if start == 'GARURA':
        need += 1; gar_counted = True

    # ---------- T1: ガルーラを場に出す(できればバトル場へ) ----------
    garura_in_play = (active == 'GARURA')
    used_paid = False
    tele_used = False
    dug_act = False; dug_nb = 0
    if active != 'GARURA':
        dug_act, dug_nb = dig_for_garura(hand, draw, active, bench, avail, hyper_t1)
        if dug_act or dug_nb:
            need += 1; mid_counted = True
        if dug_nb:
            midori_used = True; e_other += dug_nb      # ベンチのオーガポンに草が乗る(つけかえで動かせる)
        gsrc = None
        if 'GARURA' in hand: gsrc = 'hand'
        elif 'MEGASIG' in hand and 'GARURA' in avail: gsrc = 'mega'
        elif hyper_t1 and 'HYPER' in hand and 'GARURA' in avail and len(hand) >= 3: gsrc = 'hyper'
        if gsrc:
            # 退避手段(無償優先)
            def _route():
                if esc == 0: return 'free'
                if 'LATIAS' in hand: return 'latias_hand'
                if start == 'MIDORI' and (dug_act or dance_ok(hand, keep_attach=False)): return 'midori_self'
                if gsrc != 'hyper' and hyper_t1 and 'HYPER' in hand and 'LATIAS' in avail and len(hand) >= 3: return 'hyper_latias'
                if 'MIDORI' in hand and 'TSUKEKAE' in hand and dance_ok(hand, keep_attach=False) and esc == 1: return 'midori_tsuke'
                if dug_nb and 'TSUKEKAE' in hand and esc == 1: return 'midori_tsuke_dug'   # 掘ったオーガポンの草をつけかえて逃げる
                if TELEPATH_ROUTE and 'TELEPATH' in hand and 'LATIAS' in avail \
                        and (start == 'PIPPI' or 'PIPPI' in hand
                             or (start in TELEPATH_START_ONLY and gsrc == 'hand')): return 'telepath'
                if 'IREKAE' in hand: return 'irekae'
                # 2026-11-22: ガルーラをハイパーで取った番に、2枚目のハイパーでラティアスexも確保する線。
                # 無償の退避(いれかえ等)が無いときだけ使い、エネを払う退避('paid')より優先する
                if gsrc == 'hyper' and hyper_t1 >= 2 and hand.count('HYPER') >= 2 \
                        and 'LATIAS' in avail and len(hand) >= 6: return 'hyper_latias'
                if esc == 1 and any(c in ENER for c in hand) and not no_paid: return 'paid'
                return None
            route = _route()
            # 2026-11-22: 無償の前出し手段が無ければ、手札のオーガポンをベンチに出してみどりのまいで掘る
            # (オーガポン1体ごとに1回)。ハイパーでガルーラを取る場合は、そのコスト分の手札を残す
            if PROMOTE_DIG and not no_promote_dig:
                while route in (None, 'paid') and 'MIDORI' in hand and 'GRASS' in hand \
                        and (gsrc != 'hyper' or len(hand) >= 5):
                    hand.remove('MIDORI'); bench.append('MIDORI'); hand.remove('GRASS'); draw(1)
                    dug_nb += 1; e_other += 1; midori_used = True
                    if not mid_counted: need += 1; mid_counted = True
                    route = _route()
            used_paid = (route == 'paid')
            if True:
                # ガルーラ確保(先に手札から抜く)
                if gsrc == 'hand': hand.remove('GARURA')
                elif gsrc == 'mega': hand.remove('MEGASIG')
                elif gsrc == 'hyper':
                    prot = {'latias_hand':{'LATIAS'}, 'midori_tsuke':{'MIDORI','TSUKEKAE','GRASS'}, 'midori_self':{'GRASS'},
                            'irekae':{'IREKAE'}, 'telepath':{'TELEPATH','PIPPI'}, 'paid':{'GRASS','PSY','WATER','FIGHT','LIGHT','PRISM'}}.get(route, set())
                    hand.remove('HYPER'); pay_hyper(hand, CORE | prot); hyper_t1 -= 1
                if gsrc:
                    garura_in_play = True
                    if not gar_counted:
                        need += 1; gar_counted = True
                        if gsrc == 'hyper': nhyp += 1
                # 退避実行(コスト払いで必要札が落ちた稀ケースは失敗扱い)
                oknow = bool(gsrc and route)
                if not oknow: pass
                elif route == 'free':
                    need += 1                     # 逃げ0のスタート(ラティアス/コケコ)が前出しに寄与
                    if start == 'LATIAS': lat_counted = True
                elif route == 'latias_hand':
                    if 'LATIAS' in hand:
                        hand.remove('LATIAS'); bench.append('LATIAS')
                        need += 1; lat_counted = True
                    else: oknow = False
                elif route == 'midori_self' and dug_act:
                    midori_used = True                    # 掘ったときに貼った草で逃げる(追加のまいは不要)
                elif route == 'midori_self':
                    if 'GRASS' in hand:
                        midori_used = True; do_dance(hand); draw(1)   # みどりのまい(手札の草を貼って逃げコストに捨てる)
                    else: oknow = False
                    need += 1; mid_counted = True
                elif route == 'hyper_latias':
                    if 'HYPER' in hand and len(hand) >= 3:
                        hand.remove('HYPER'); pay_hyper(hand, {'GARURA'}); hyper_t1 -= 1
                        bench.append('LATIAS')
                        need += 1; nhyp += 1; lat_counted = True
                    else: oknow = False
                elif route == 'midori_tsuke':
                    if 'MIDORI' in hand and 'TSUKEKAE' in hand and 'GRASS' in hand:
                        hand.remove('MIDORI'); bench.append('MIDORI'); midori_used = True; do_dance(hand); draw(1)
                        need += 1; mid_counted = True
                        if 'TSUKEKAE' in hand: hand.remove('TSUKEKAE')
                    else: oknow = False
                elif route == 'irekae':
                    if 'IREKAE' in hand: hand.remove('IREKAE')
                    else: oknow = False
                elif route == 'telepath':
                    if 'TELEPATH' in hand and (start == 'PIPPI' or 'PIPPI' in hand or start in TELEPATH_START_ONLY):
                        if start != 'PIPPI' and start not in TELEPATH_START_ONLY:
                            hand.remove('PIPPI'); bench.append('PIPPI')
                        hand.remove('TELEPATH'); tele_used = True
                        bench.append('LATIAS')      # 山札から(サイド落ちでない前提は avail で判定済み)
                        need += 1; lat_counted = True
                    else: oknow = False
                elif route == 'midori_tsuke_dug':
                    if 'TSUKEKAE' in hand: hand.remove('TSUKEKAE'); e_other -= 1
                    else: oknow = False
                elif route == 'paid':
                    if any(c in ENER for c in hand):
                        for c in list(hand):
                            if c in ENER: hand.remove(c); break
                        paid = True
                    else: oknow = False
                if dug_act and route != 'midori_self':
                    e_other += 1; midori_used = True      # バトル場のオーガポンに草が残る
                if oknow:
                    bench.append(active)
                    active = 'GARURA'

    cond1 = (active == 'GARURA') and not paid
    if stats is not None:
        # 条件1の内訳(診断用。判定そのものには影響しない)
        if start == 'GARURA':            stats['c1_ガルーラスタート'] += 1
        elif cond1:                      stats['c1_達成_無償退避'] += 1
        elif not garura_in_play:         stats['c1_未達_ガルーラを確保できない'] += 1
        elif paid:                       stats['c1_未達_手張りを退避に使うしかない'] += 1
        else:                            stats['c1_未達_逃がせない'] += 1
    zaijou = garura_in_play          # ガルーラが場にいる(バトル場でもベンチでも)
    if not zaijou:
        return cond1, False, None, used_paid, d
    if active != 'GARURA' and 'GARURA' not in bench:
        bench.append('GARURA')

    # ---------- T1 残りの展開 ----------
    if active == 'GARURA': draw(2)   # おつかいダッシュ(バトル場のときのみ)
    if T1_SNAP is not None:
        T1_SNAP.update(hand=list(hand), bench=list(bench), active=active, tele_used=tele_used,
                       paid=paid, hyper_t1=hyper_t1, nhyp=nhyp, avail=set(deck))
    if 'MIDORI' not in bench and 'MIDORI' in hand:
        hand.remove('MIDORI'); bench.append('MIDORI')
    if 'MIDORI' in bench and not midori_used and dance_ok(hand):
        midori_used = True; do_dance(hand); e_other += 1; draw(1)
        if not mid_counted: need += 1; mid_counted = True
    firo_in_play = False
    if 'FIRO' in hand:
        hand.remove('FIRO'); firo_in_play = True; need += 1
    elif hyper_t1 and 'HYPER' in hand and 'FIRO' in avail and len(hand) >= 3:
        hand.remove('HYPER'); pay_hyper(hand, CORE); hyper_t1 -= 1
        firo_in_play = True; need += 1; nhyp += 1
    if 'LATIAS' in hand:
        hand.remove('LATIAS'); bench.append('LATIAS')
        if not lat_counted: need += 1; lat_counted = True
    if not paid and not tele_used:
        for c in list(hand):
            if c in ENER:
                hand.remove(c)
                if firo_in_play: e_firo += 1
                else: e_other += 1
                break

    # ---------- T2 ----------
    draw(1)
    if active == 'GARURA': draw(2)   # おつかいダッシュ
    if 'MIDORI' not in bench and 'MIDORI' in hand:
        hand.remove('MIDORI'); bench.append('MIDORI')
    if 'MIDORI' in bench and dance_ok(hand):
        do_dance(hand); e_other += 1; draw(1)
        if not mid_counted: need += 1; mid_counted = True
    latias_in_play = 'LATIAS' in bench
    esc_active = 3 if active == 'GARURA' else ({'LATIAS':0,'KAPU':0}.get(active, 1))
    if latias_in_play: esc_active = 0
    avail = set(deck)
    hyper_left = min(HYPER_T2_MAX, hand.count('HYPER'))   # 先攻T2のハイパー使用可能枚数(2026-11-22: 1→2)

    # サポート候補(現物 / ニャース経由): (サポート, hyperコスト, ポケモン新規計上)
    cands = [(None, 0, 0)]
    for s in ('AKAMATSU','CYRANO'):
        if s in hand: cands.append((s, 0, 0))
        elif 'NYASU' in hand and s in avail: cands.append((s, 0, 1))
        elif hyper_left and 'NYASU' in avail and s in avail and len(hand) >= 3: cands.append((s, 1, 1))
    ok = False
    for s, hc, pk in cands:
        ok = feas(hand, firo_in_play, e_firo, e_other, latias_in_play, avail,
                  hyper_left, s, esc_active, sup_hyper_cost=hc, sup_poke=pk,
                  need=need, nhyp=nhyp)
        if ok: break
    if not ok:
        # リーリエの決心フォールバック
        lil = None
        if 'LILLIE' in hand: lil = (0, 0)
        elif 'NYASU' in hand and 'LILLIE' in avail: lil = (0, 1)
        elif hyper_left and 'NYASU' in avail and 'LILLIE' in avail and len(hand) >= 4: lil = (1, 1)
        if lil and hyper_ok(need + lil[1], nhyp + lil[0]):
            hc, pk = lil
            if 'LILLIE' in hand: hand.remove('LILLIE')
            deck.extend(hand); hand.clear(); rnd.shuffle(deck)
            draw(8)
            avail = set(deck)
            hl2 = max(0, min(hyper_left - hc, hand.count('HYPER')))
            ok = feas(hand, firo_in_play, e_firo, e_other, latias_in_play, avail,
                      hl2, None, esc_active, need=need + pk, nhyp=nhyp + hc)
    return cond1, True, ok, used_paid, d


def trial(deck_template, rnd, deal=None, stats=None):
    """条件1・条件2の判定。

    2026-09-16 追加: 先1に「エネを切って逃げる」しか退避手段が無い場合、モデルは既定でエネを払って
    ガルーラを前に出す(=その番の手張りなし)。条件2については、ガルーラを前に出さず手張りを
    ファイアローexに回すルートも評価し、どちらかで成立すれば達成とする。
    条件1はこの分岐の影響を受けない(どちらのルートでも条件1は未達)。
    別ルートの評価は配りから決まる専用の乱数を使い、呼び出し元の rnd を消費しない。
    """
    c1, z, ok, used_paid, d = _trial(deck_template, rnd, deal, stats)
    if used_paid and not ok:
        alt_rnd = random.Random(','.join(d))
        _, z2, ok2, _, _ = _trial(deck_template, alt_rnd, d, None, no_paid=True)
        if z2 and ok2:
            z, ok = True, True
            if stats is not None: stats['c2_救済_手張りをファイアローに温存'] += 1
    # 2026-11-22: 先攻T1でハイパー2枚使う線を選んだ結果、旧来(T1は1枚まで)の線より条件2が悪化する配りが
    # あるため、条件2は「最善手」の前提で旧来のT1の線でも評価し、どちらかで成立すれば達成とする。
    # (規約を緩めた結果として値が下がらないことを保証する)条件1は新しい線で評価(単調に増える)。
    # リーリエ採用デッキでは、引き直しのランダム性により2つの線のORが二重引き直しになり過大評価となるため、再評価は行わない(リーリエ0枚のデッキでは試行が配りだけで決まるので問題ない)。
    # 2026-11-22: 前出し手段を掘るためにみどりのまいで草を使った結果、条件2が悪化する配りがあるため、
    # 掘らない線でも評価してどちらかで成立すれば達成とする(最善手評価。リーリエ採用デッキでは行わない)
    if PROMOTE_DIG and 'LILLIE' not in deck_template and not (z and ok):
        alt_rnd = random.Random(','.join(d) + '|nopd')
        _, z4, ok4, up4, _ = _trial(deck_template, alt_rnd, d, None, no_promote_dig=True)
        if up4 and not ok4:
            _, z4, ok4, _, _ = _trial(deck_template, random.Random(','.join(d) + '|nopdnp'), d, None, no_paid=True, no_promote_dig=True)
        if z4 and ok4:
            z, ok = True, True
            if stats is not None: stats['c2_救済_前出しを掘らない線'] += 1
    if HYPER_T1_MAX > 1 and 'LILLIE' not in deck_template and not (z and ok):
        alt_rnd = random.Random(','.join(d) + '|cap1')
        _, z3, ok3, up3, _ = _trial(deck_template, alt_rnd, d, None, t1_cap=1)
        if up3 and not ok3:
            _, z3, ok3, _, _ = _trial(deck_template, random.Random(','.join(d) + '|cap1np'), d, None, no_paid=True, t1_cap=1)
        if z3 and ok3:
            z, ok = True, True
            if stats is not None: stats['c2_救済_旧T1ルート'] += 1
    return c1, z, ok

def run(counts, trials, seed):
    tmpl = []
    for k, v in counts.items(): tmpl += [k] * v
    assert len(tmpl) == 60, len(tmpl)
    rnd = random.Random(seed)
    n1 = nz = n2 = 0
    for _ in range(trials):
        c1, z, ok = trial(tmpl, rnd)
        n1 += c1; nz += z
        if z and ok: n2 += 1
    return n1 / trials * 100, nz / trials * 100, (n2 / nz * 100 if nz else 0), n2 / trials * 100

if __name__ == '__main__':
    T = int(sys.argv[1]) if len(sys.argv) > 1 else 200000
    for name, cfg in (('現行(2026-09-12更新後)', CUR), ('旧リスト', OLD)):
        c1, z, c2c, c2u = run(cfg, T, 12345)
        print(f'{name}: 条件1={c1:.1f}%  ガルーラ在場={z:.1f}%  条件2条件付={c2c:.1f}%  条件2無条件={c2u:.1f}%')
