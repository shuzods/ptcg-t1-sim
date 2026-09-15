# 後攻T1(後1)の確率計算 v2
#   条件5: ファイアローexが後1に技宣言(無色2)
#   条件6: メガガルーラexが後1に技宣言(無色3)・アカマツ使用
#
# v2 の変更(自己レビューで発見した欠落の修正):
#   - ガルーラの確保にシアノ/リーリエ経由を追加(v1はハイパー/メガシグナル/現物のみで、
#     ガルーラが引けない試行を即失敗にしていた)
#   - シアノでオーガポンみどりのめんex(ポケモンex)を確保して草を供給する経路を追加
#   - 条件5にハイパーボール→オーガポンの草供給を追加
#   - サポートプラン(None/アカマツ/シアノ/暗号マニア/リーリエ)×いれかえ先出しの有無=10本を
#     1試行ごとに評価し、条件ごとに成立する線があれば達成とする(後1は1ターン内で完結するため、
#     手順選択に先読みは不要=この扱いは妥当)
#
# 共通: 手張り1回/サポート1枚/ハイパーボール1回。ポケモンいれかえは"逃げる"ではないため
#       無償退避1回とは別枠で併用可。条件6はエネを切って逃げる動き不採用(切ると3枚に届かない)。
import random, sys
from collections import Counter
from sim import BASICS, ENER, ESC, pay_hyper, pick_start, CORE, dance_ok, do_dance

BASIC_EN = ('GRASS', 'PSY', 'WATER', 'FIGHT', 'LIGHT')   # プリズムはアカマツ対象外
EX_POKE = ('GARURA', 'FIRO', 'LATIAS', 'MIDORI')          # シアノで持ってこられる範囲(本条件で使う分)

# 「全員ハイパーNG」の解釈。先攻v2(2026-09-12)では共通規約の文言「複数の異なるポケモンを
# 同時に揃える条件では」に従い、必要ポケモンが1体だけの局面には制約を適用しない。
# 後攻v1/v2 は1体の局面にも適用する保守的な実装だったため、フラグで切替可能にした。
SINGLE_POKE_HYPER_OK = True

def blocked(tot_p, tot_h):
    """True なら「全員ハイパー」に該当し、その組み合わせは不可"""
    if tot_p == 0: return False
    if tot_p == 1 and SINGLE_POKE_HYPER_OK: return False
    return tot_h >= tot_p

def sup_access(s, hand, deck_set, hyper_left):
    """サポート s を撃てるか。戻り値: 必要ハイパー枚数 or None"""
    if s in hand: return 0
    if 'NYASU' in hand and s in deck_set: return 0
    if hyper_left and 'NYASU' in deck_set and s in deck_set and len(hand) >= 4: return 1
    return None

class Line:
    """後1の1本のプレイ線"""
    def __init__(self, hand, deck, start, rnd):
        self.hand = list(hand); self.deck = list(deck); self.rnd = rnd
        self.active = start; self.bench = []
        self.retreat_used = False
        self.need_poke = 0        # このプランが必要とするポケモンの数
        self.hyper_poke = 0       # うちハイパーボールで賄った数
        self.dash_used = False; self.dance_used = False
        self.grass = 0; self.sup_used = False
        self._gar_counted = False
        if start == 'GARURA':                 # バトル場スタート=現物で用意できている
            self.need_poke = 1; self._gar_counted = True

    def draw(self, n=1):
        for _ in range(n):
            if self.deck: self.hand.append(self.deck.pop(0))

    def dset(self): return set(self.deck)

    def take(self, card):
        """山札からサーチして手札へ"""
        if card in self.deck: self.deck.remove(card); self.hand.append(card); return True
        return False

    def esc_active(self):
        if 'LATIAS' in self.bench: return 0
        return ESC.get(self.active, 1)

    def gar_in_play(self):
        return self.active == 'GARURA' or 'GARURA' in self.bench

    def use_hyper(self, card):
        if 'HYPER' in self.hand and card in self.deck and len(self.hand) >= 3:
            self.hand.remove('HYPER'); pay_hyper(self.hand, CORE)
            return self.take(card)
        return False

    def get_garura(self):
        if self.gar_in_play():
            if not self._gar_counted: self.need_poke += 1; self._gar_counted = True
            return True
        if 'GARURA' in self.hand:
            self.hand.remove('GARURA'); self.bench.append('GARURA')
            self.need_poke += 1; self._gar_counted = True; return True
        if 'MEGASIG' in self.hand and 'GARURA' in self.deck:
            self.hand.remove('MEGASIG'); self.deck.remove('GARURA'); self.bench.append('GARURA')
            self.need_poke += 1; self._gar_counted = True; return True
        if self.use_hyper('GARURA'):
            self.hand.remove('GARURA'); self.bench.append('GARURA')
            self.need_poke += 1; self.hyper_poke += 1; self._gar_counted = True; return True
        return False

    def play_supporter(self, s):
        """サポート s を実際にプレイする(現物/ニャース経由/ハイパー→ニャース)。使用時点で再判定する"""
        if self.sup_used: return False
        if s in self.hand:
            self.hand.remove(s); self.sup_used = True; return True
        if 'NYASU' in self.hand and s in self.deck:
            self.hand.remove('NYASU'); self.bench.append('NYASU')
            if self.take(s):
                self.hand.remove(s); self.sup_used = True; return True
            return False
        if 'HYPER' in self.hand and 'NYASU' in self.deck and s in self.deck and len(self.hand) >= 4:
            if self.use_hyper('NYASU') and 'NYASU' in self.hand:
                self.hand.remove('NYASU'); self.bench.append('NYASU')
                if self.take(s):
                    self.hand.remove(s); self.sup_used = True; return True
        return False

    def bench_latias(self):
        if 'LATIAS' in self.hand:
            self.hand.remove('LATIAS'); self.bench.append('LATIAS')

    def promote_garura(self, use_irekae):
        """ガルーラをバトル場へ(無償のみ)"""
        if self.active == 'GARURA': return True
        if 'GARURA' not in self.bench: return False
        if self.esc_active() == 0 and not self.retreat_used:
            self.bench.remove('GARURA'); self.bench.append(self.active)
            self.active = 'GARURA'; self.retreat_used = True; return True
        if use_irekae and 'IREKAE' in self.hand:
            self.hand.remove('IREKAE'); self.bench.remove('GARURA'); self.bench.append(self.active)
            self.active = 'GARURA'; return True
        return False

    def dash(self):
        if self.active == 'GARURA' and not self.dash_used:
            self.dash_used = True; self.draw(2)

    def setup_midori(self):
        if not self.midori_in_play() and 'MIDORI' in self.hand:
            self.hand.remove('MIDORI'); self.bench.append('MIDORI')
        if self.midori_in_play() and not self.dance_used and dance_ok(self.hand):
            # みどりのまいは手札の基本草エネを消費する(2026-09-15 修正)
            self.dance_used = True; do_dance(self.hand); self.grass += 1; self.draw(1)

    def midori_in_play(self):
        return 'MIDORI' in self.bench or self.active == 'MIDORI'

    # ---------- 判定 ----------
    def final5(self, akamatsu):
        """ファイアローが無色2でバトル場に立てるか
        各選択肢は (ハイパー使用数, ポケモン必要数, ...) を持ち、
        「必要ポケモン全員がハイパー」になる組み合わせは規約により除外する"""
        ds = self.dset()
        n_en = sum(1 for c in self.hand if c in ENER)
        tsuke = self.hand.count('TSUKEKAE')
        nh = self.hand.count('HYPER')
        if akamatsu and len({c for c in ds if c in BASIC_EN}) < 2: return False
        # 本体 (hyper, poke)
        firo = []
        if 'FIRO' in self.hand: firo.append((0, 1))
        if 'FIRO' in ds: firo.append((1, 1))
        if not firo: return False
        # 草(つけかえ用) (hyper, poke)
        grass_src = []
        if self.grass >= 1: grass_src.append((0, 0))
        elif self.midori_in_play() and 'GRASS' in self.hand: grass_src.append((0, 0))
        elif 'MIDORI' in self.hand and 'GRASS' in self.hand: grass_src.append((0, 1))
        elif 'MIDORI' in ds and 'GRASS' in self.hand: grass_src.append((1, 1))
        # 前出し (hyper, poke, 手張りを退避に消費, 草を消費)
        front = []
        if 'IREKAE' in self.hand: front.append((0, 0, False, False))
        if 'LATIAS' in self.bench and not self.retreat_used: front.append((0, 0, False, False))
        if 'LATIAS' in ds and not self.retreat_used: front.append((1, 1, False, False))
        if not self.retreat_used and self.esc_active() == 1 and (n_en >= 1 or akamatsu):
            front.append((0, 0, True, False))
        if not self.retreat_used and self.active == 'MIDORI' and self.grass >= 1:
            front.append((0, 0, False, True))
        if not front: return False
        hand_en = n_en + (1 if akamatsu else 0)
        for hf, pf in firo:
            for hr, pr, paid, gcut in front:
                for hg, pg in (grass_src or [(0, 0)]):
                    use_grass = bool(grass_src) and not gcut
                    hgg = hg if use_grass else 0
                    pgg = pg if use_grass else 0
                    uh = hf + hr + hgg
                    if uh > nh or len(self.hand) < 2 * uh + 1: continue
                    tot_h = self.hyper_poke + uh
                    tot_p = self.need_poke + pf + pr + pgg
                    if blocked(tot_p, tot_h): continue          # 全員ハイパーNG
                    e = 1 if akamatsu else 0
                    if not paid and hand_en >= 1: e += 1
                    if use_grass and tsuke >= 1: e += 1
                    if e >= 2: return True
        return False

    def final6(self):
        """ガルーラが無色3(アカマツ+手張り+草つけかえ)でバトル場に立てるか"""
        ds = self.dset()
        if 'TSUKEKAE' not in self.hand: return False, 'MOVE'
        if len({c for c in ds if c in BASIC_EN}) < 2: return False, 'AKAMATSU_TYPES'
        nh = self.hand.count('HYPER')
        if self.grass >= 1 or (self.midori_in_play() and 'GRASS' in self.hand):
            gc, pg = 0, 0
        elif 'MIDORI' in self.hand and 'GRASS' in self.hand:
            gc, pg = 0, 1
        elif nh > 0 and 'MIDORI' in ds and 'GRASS' in self.hand:
            gc, pg = 1, 1
        else:
            return False, 'GRASS'
        if self.active == 'GARURA': pc, pp = 0, 0
        elif 'GARURA' not in self.bench: return False, 'PROMOTE'
        elif 'IREKAE' in self.hand: pc, pp = 0, 0
        elif 'LATIAS' in self.bench and not self.retreat_used: pc, pp = 0, 0
        elif nh - gc > 0 and 'LATIAS' in ds and not self.retreat_used: pc, pp = 1, 1
        else: return False, 'PROMOTE'
        uh = gc + pc
        if uh > nh or len(self.hand) < 2 * uh + 1: return False, 'HYPER_CONFLICT'
        tot_h = self.hyper_poke + uh
        tot_p = self.need_poke + pg + pp
        if blocked(tot_p, tot_h): return False, 'HYPER_CONFLICT'
        return True, None

ANGO_ORDER = ('FIRO', 'TSUKEKAE', 'IREKAE', 'MIDORI', 'GRASS')

def run_line(hand0, deck0, start, plan, use_irekae, rnd, stats):
    """1本のプレイ線を実行して (ok5, ok6, 条件6の未達理由) を返す"""
    L = Line(hand0, deck0, start, rnd)

    # --- シアノ: 必要なポケモンexを最大3枚まとめて確保(最初に撃つ) ---
    if plan == 'CYRANO':
        if not L.play_supporter('CYRANO'): return False, False, None
        picks = []
        if not L.gar_in_play() and 'GARURA' not in L.hand: picks.append('GARURA')
        if 'FIRO' not in L.hand: picks.append('FIRO')
        if 'IREKAE' not in L.hand and 'LATIAS' not in L.hand and 'LATIAS' not in L.bench: picks.append('LATIAS')
        if not L.midori_in_play() and 'MIDORI' not in L.hand: picks.append('MIDORI')
        for c in picks[:3]: L.take(c)

    # --- リーリエの決心: 無償の展開を先に済ませてから撃つ ---
    if plan == 'LILLIE':
        L.get_garura(); L.bench_latias(); L.promote_garura(use_irekae); L.dash(); L.setup_midori()
        if not L.play_supporter('LILLIE'): return False, False, None
        L.deck.extend(L.hand); L.hand.clear(); rnd.shuffle(L.deck); L.draw(8)

    # --- 暗号マニアの解読: ドロー前に不足パーツを山上に積む ---
    if plan == 'ANGO':
        L.get_garura(); L.bench_latias(); L.promote_garura(use_irekae)
        draws = (2 if (L.active == 'GARURA' and not L.dash_used) else 0) \
                + (1 if (L.midori_in_play() or 'MIDORI' in L.hand) and not L.dance_used else 0)
        if draws < 1: return False, False, None
        if not L.play_supporter('ANGO'): return False, False, None
        need = []
        if 'FIRO' not in L.hand: need.append('FIRO')
        if 'TSUKEKAE' not in L.hand: need.append('TSUKEKAE')
        if 'IREKAE' not in L.hand and 'LATIAS' not in L.bench: need.append('IREKAE')
        if not L.midori_in_play() and 'MIDORI' not in L.hand: need.append('MIDORI')
        if not any(c in ENER for c in L.hand): need.append('GRASS')
        for c in [x for x in ANGO_ORDER if x in need][:min(2, draws)]:
            L.take(c)

    # --- 共通の無償展開 ---
    L.get_garura()
    L.bench_latias()
    L.promote_garura(use_irekae)
    L.dash()
    L.bench_latias()
    L.setup_midori()
    if not L.gar_in_play():
        return False, False, 'NO_GARURA'

    ok6 = False; why = None
    if plan == 'AKAMATSU':
        got = L.play_supporter('AKAMATSU')
        ok5 = L.final5(akamatsu=got)
        if got: ok6, why = L.final6()
        else: why = 'AKAMATSU'
    else:
        ok5 = L.final5(akamatsu=False)
    return ok5, ok6, why

PLANS = (None, 'AKAMATSU', 'CYRANO', 'ANGO', 'LILLIE')

def trial_back(tmpl, rnd, stats, deal=None):
    if deal is not None:
        d = list(deal)
    else:
        d = tmpl[:]
        rnd.shuffle(d)
        while not any(c in BASICS for c in d[:7]):
            rnd.shuffle(d)
    hand = list(d[:7]); deck = d[13:]
    start = pick_start([c for c in hand if c in BASICS])
    hand.remove(start)
    if deck: hand.append(deck.pop(0))          # ターン頭ドロー

    ok5 = ok6 = False; whys = []
    for plan in PLANS:
        for ui in (False, True):
            a, b, why = run_line(hand, deck, start, plan, ui, rnd, stats)
            ok5 = ok5 or a; ok6 = ok6 or b
            if why: whys.append(why)
            if ok5 and ok6: break
        if ok5 and ok6: break
    if not ok6 and whys:
        for w in ('NO_GARURA', 'MOVE', 'GRASS', 'AKAMATSU', 'PROMOTE', 'HYPER_CONFLICT', 'AKAMATSU_TYPES'):
            if w in whys: stats['c6_' + w] += 1; break
    return ok5, ok6

def run_back(counts, trials, seed=9001):
    tmpl = []
    for k, v in counts.items(): tmpl += [k] * v
    assert len(tmpl) == 60
    rnd = random.Random(seed)
    stats = Counter(); n5 = n6 = nu = 0
    for _ in range(trials):
        a, b = trial_back(tmpl, rnd, stats)
        n5 += a; n6 += b; nu += (a or b)
    f = lambda x: x / trials * 100
    return f(n5), f(n6), f(nu), stats, trials

if __name__ == '__main__':
    from decks import OLD, CUR
    T = int(sys.argv[1]) if len(sys.argv) > 1 else 200000
    for name, cfg in (('現行', CUR), ('旧リスト', OLD)):
        a, b, u, st, T2 = run_back(cfg, T)
        print(f'{name}: 条件5(後1ファイアロー)={a:.1f}%  条件6(後1ガルーラ・アカマツ)={b:.1f}%  いずれか={u:.1f}%')
        print('   ' + ' '.join(f'{k}:{v/T2*100:.1f}' for k, v in st.most_common()))
