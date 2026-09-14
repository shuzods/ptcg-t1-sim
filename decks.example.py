# decks.py の雛形。実際のデッキリストに差し替えて decks.py という名前で置く。
# カード記号は sim.py の BASICS / ENER / JUNK / CORE と対応させること。
# 合計60枚でないと各スクリプトの assert で落ちる。

CUR = {
 'GARURA':4,'PIPPI':2,'NYASU':2,'LATIAS':2,'KICHI':1,'IDO':1,'KAPU':1,'NAGE':1,'PAO':1,'MIDORI':3,
 'FIRO':2,
 'HYPER':4,'MEGASIG':2,'IREKAE':2,'TSUKEKAE':4,'TANKA':1,'STAMP':1,
 'AKAMATSU':3,'BOSS':2,'LILLIE':2,'CYRANO':1,'JUDGE':1,'ANGO':1,
 'CAVERN':3,
 'GRASS':7,'PSY':2,'WATER':1,'FIGHT':1,'LIGHT':1,'PRISM':1,
}

# 比較用の過去リストがあれば同様に定義する
OLD = dict(CUR)
MID = dict(CUR)
