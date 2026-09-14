# ptcg-t1-sim

ポケモンカード(スタンダード)の「1ターン目にやりたいことができる確率」を求めるモンテカルロ・シミュレータ。

デッキ固有の情報(採用カードと枚数)は **このリポジトリに含まれない**。`decks.py` を別途用意する。

## ファイル

| ファイル | 内容 |
|---|---|
| `sim.py` | T1エンジン本体・共通関数(`hyper_ok` / `pay_hyper` / `pick_start`)+ 条件1・条件2 |
| `sim3.py` | 条件3 |
| `sim4.py` | 条件4 |
| `sim_back.py` | 後攻T1の条件5・条件6 |
| `compare.py` | 複数構成を条件1〜6+先後の「いずれか達成」で横並び比較 |
| `driver.py` | 制約あり/なしの差分、構造テスト、`variant()` による構築変更検証 |
| `decks.example.py` | `decks.py` の雛形 |

## 使い方

```bash
git clone --depth 1 https://github.com/<user>/ptcg-t1-sim.git
cd ptcg-t1-sim
cp decks.example.py decks.py     # 中身を実際のデッキリストに差し替える
python3 compare.py 300000
```

`decks.py` は `{カード記号: 枚数}` の辞書を定義するだけ。合計60枚でないと `assert` で落ちる。
構築変更を試すときは `compare.variant(CUR, TSUKEKAE=3, ...)` を使う。抜いた枚数は
無関係なトレーナーズ `FILLER` で自動補填され、60枚が維持される。

## 前提・規約

計算規約(マリガンの扱い、ハイパーボールの使用上限、「必要ポケモン全員をハイパーボールで
賄うのは不可」という制約、各条件の定義など)は、このリポジトリの外に置いた仕様書で管理している。
コード中のコメントはその要約。
