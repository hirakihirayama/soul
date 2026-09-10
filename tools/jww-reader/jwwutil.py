# -*- coding: utf-8 -*-
"""JWW を読んだあとの前処理ユーティリティ。

README の「JWW を機械で読むときに踏む罠」に対応する。
パーサ（jwwread）とは独立していて、中間表現の辞書だけを扱う。
標準ライブラリのみ。
"""
import collections
import unicodedata


def _key(e):
    """要素の同一性を表すキー。

    **座標フィールドはクラスごとに違う。**円弧は x1/y1 を持たず cx/cy/rad で
    表される。x1/y1/x2/y2 だけでキーを作ると、同一レイヤの円弧が全部 1 つに
    潰れて大量の要素が消える（実際にそうなっていた）。ここでは中間表現の
    数値・文字フィールドを全部たどることで、クラスごとの違いを気にせずに済ませる。

    含めるもの: クラス名・レイヤ・レイヤグループ・線色・線種・全ての幾何値・本文
    含めないもの: 曲線属性グループ番号(group)・属性フラグ(flg)
      この 2 つは見た目の同一性と関係がなく、二重書きの片方だけ値が違うことが
      あるため。
    """
    out = [e.get('kind')]
    for k in sorted(e):
        if k in ('kind', 'group', 'flg'):
            continue
        v = e[k]
        if isinstance(v, float):
            out.append((k, round(v, 3)))
        elif isinstance(v, dict):
            out.append((k, _key(v)))
        elif isinstance(v, (list, tuple)):
            out.append((k, tuple(_key(x) if isinstance(x, dict) else x for x in v)))
        else:
            out.append((k, v))
    return tuple(out)


def dedupe(ents):
    """罠3: 幾何的に完全一致する要素を落とす。

    同じ要素が同じ座標に 2 つ入っている図面がある。Archicad から出力した JWW は
    文字・線を系統的に二重に書くが、**それ以外の作図系統でも重ね書きは起きる**
    （実測 159 本すべてに 1 件以上あった）。素直に読むと通り芯ラベルが重複して
    見え、重複を除く処理に全部かかって通り芯が 1 本も取れなくなる。壁の未ペア線も
    倍に数えられる。

    座標は小数 3 桁で丸めて比較する。**内容まで一致するものだけ**を落とす。
    同じ座標に違う文字が重なっている場合は罠 6 で、こちらでは落ちない
    （overlapping_texts() で拾う）。

    落とすかどうかは用途による。図面をそのまま描き直すなら落とす必要はない。
    数を数える用途（本数・延長・面積）では落とさないと倍に出る。
    """
    seen, out = set(), []
    for e in ents:
        k = _key(e)
        if k in seen:
            continue
        seen.add(k)
        out.append(e)
    return out


def overlapping_texts(ents, tol=0.05):
    """罠6: 同じ座標に内容の違う文字が重なっているものを返す。

    作図時の修正で古い文字を消し忘れ、新しい文字を真上に書いた図面がある。
    Jw_cad の画面では後から描いた方が上に重なるので、人間には見えない。

    **どちらが正しいかは機械には決められない。**返り値は人間に見せるための
    ものであり、自動でどちらかを採ってはいけない。黙って片方を採ると、
    間違いが検算を通り抜けて最後まで残る。

    tol は同一座標とみなす図面上mmの許容差。
    **dedupe() を先に通すこと。**通していないと罠3の二重書きが同じ組に
    混ざり、人間に見せる一覧が読みにくくなる。
    返り値: [((glayer, layer, x, y), [文字要素, ...]), ...]
    """
    q = 1.0 / tol if tol else 1.0
    bag = collections.defaultdict(list)
    for e in ents:
        if e['kind'] != 'CDataMoji':
            continue
        bag[(e['glayer'], e['layer'],
             round(e['x1'] * q) / q, round(e['y1'] * q) / q)].append(e)
    out = [(k, g) for k, g in bag.items()
           if len({x.get('text') for x in g}) > 1]
    return sorted(out)


# Jw_cad が図面に書き込む設定文字のキー接頭辞（実測）
SETTING_PREFIX = ('Printer_', 'Draw_', 'View_', 'Dim_', 'Write_', 'Jw_',
                  'Grid_', 'Snap_')


def is_setting_text(e):
    """罠9: Jw_cad 自身が書き込んだ設定文字かどうか。

    Jw_cad は印刷・表示の設定を "Printer_PaperSize = 0" のような文字要素として
    図面に書き込む。**図面枠のレイヤグループに入るとは限らず、図面本体のレイヤに
    紛れることがある**（実測 159 本のうち 50 本に混入。うち何本かは (0,0) など
    部材の載っているレイヤ）。

    文字を総ざらいして符号や注記を集める処理では、これを落とさないと
    存在しない符号を拾う。
    """
    if e.get('kind') != 'CDataMoji':
        return False
    t = e.get('text') or ''
    return ' = ' in t and t.startswith(SETTING_PREFIX)


def drop_setting_texts(ents):
    """罠9: Jw_cad の設定文字を除いた要素列を返す。"""
    return [e for e in ents if not is_setting_text(e)]


# NFKC は ｘ・Ｘ を半角にするが × (U+00D7) は変換しないので個別に置換する
_MULT = {'X': 'x', '×': 'x'}


def normalize(s):
    """罠8: 文字を突合できる形に正規化する。

    断面表記の掛け算記号は x（半角エックス）・ｘ（全角エックス）・
    ×（全角の乗算記号）が混在し、同じ図面の中でも揺れる。数字にも全角が
    混じる。`300x1800` で検索して `300×1800` が漏れるのを防ぐ。
    """
    if s is None:
        return None
    s = unicodedata.normalize('NFKC', s)
    return ''.join(_MULT.get(c, c) for c in s)
