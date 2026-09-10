#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""jww-reader のコマンドライン入口。

    python3 jww.py info    FILE.jww
    python3 jww.py verify  FILE.jww
    python3 jww.py probe   FILE.jww [--win=x0,x1,y0,y1] [--texts=G,L] [--all-texts]
    python3 jww.py svg     FILE.jww OUT.svg
    python3 jww.py pdf     FILE.jww OUT.pdf     # reportlab が必要
    python3 jww.py json    FILE.jww OUT.json

どのディレクトリから実行してもよい（自分の場所を sys.path に入れる）。
"""
import os
import re
import sys
import json
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jwwread   # noqa: E402
import jwwutil   # noqa: E402

KIND = {'CDataSen': '線', 'CDataEnko': '円弧', 'CDataMoji': '文字',
        'CDataSolid': 'ソリッド', 'CDataTen': '点', 'CDataSunpou': '寸法',
        'CDataBlock': 'ブロック'}
ZUMEN = {0: 'A0', 1: 'A1', 2: 'A2', 3: 'A3', 4: 'A4'}
# 符号らしい文字列（英字1〜4 + 数字1〜3、末尾に英字1つまで）
CODEISH = re.compile(r'^[A-Za-z]{1,4}[0-9]{1,3}[A-Za-z]?$')
# 図題らしい文字列
TITLEISH = re.compile(r'(伏図|軸組|リスト|詳細図|配筋|仕様|平面|断面|立面|階)')


def _bbox(ents):
    xs = [e['x1'] for e in ents if 'x1' in e]
    ys = [e['y1'] for e in ents if 'y1' in e]
    if not xs:
        return None
    return min(xs), max(xs), min(ys), max(ys)


def _in_win(e, win):
    if win is None:
        return True
    x0, x1, y0, y1 = win
    return x0 <= e.get('x1', 0) <= x1 and y0 <= e.get('y1', 0) <= y1


def cmd_info(ir, path):
    print(f'{os.path.basename(path)}')
    print(f'  データ形式バージョン : {ir["version"]}'
          f'  (MFC スキーマ番号 {ir.get("schema")})')
    print(f'  用紙サイズ           : {ZUMEN.get(ir["zumen"], "?")} (zumen={ir["zumen"]})')
    if ir.get('memo'):
        print(f'  メモ                 : {ir["memo"]!r}')
    print(f'  宣言要素数           : {ir["declared"]:,}')
    print(f'  読み取り要素数       : {len(ir["entities"]):,}')
    print(f'  末尾残バイト         : {ir["trailing_bytes"]:,}')
    nimg = sum(1 for e in ir['entities']
               if e['kind'] == 'CDataMoji' and (e.get('text') or '').startswith('^@BM'))
    if nimg:
        print(f'  埋め込み画像         : {nimg} 件（画像データは末尾に残る）')

    cnt = collections.Counter(e['kind'] for e in ir['entities'])
    print('  クラス別件数:')
    for k, n in cnt.most_common():
        print(f'    {KIND.get(k, k):<8} {n:>8,}')

    used = sorted({e['glayer'] for e in ir['entities']})
    print('  使用中のレイヤグループと公称縮尺:')
    for g in used:
        name = ir['glayers'][g] if g < len(ir.get('glayers') or []) else ''
        n = sum(1 for e in ir['entities'] if e['glayer'] == g)
        print(f'    {g:>2}  1/{ir["scale"].get(g, 0):<8g} 要素{n:>8,}  {name}')
    if not ir.get('glayers'):
        print('    ※ このバージョンではレイヤ名・レイヤグループ名を取得しない')
    print('  ※ 公称縮尺は当てにならない図面がある。寸法文字で検算すること（罠2）')


def cmd_verify(path):
    """検算。宣言数＝実読数と末尾残を確認する。異常があれば終了コード1。"""
    ng = []
    print(f'{os.path.basename(path)}')
    try:
        with open(path, 'rb') as f:
            head = f.read(8)
    except OSError as ex:
        print(f'  NG 開けない: {ex}')
        return 1
    if head != b'JwwData.':
        print(f'  NG 先頭8バイトが JwwData. でない: {head!r}')
        print('     → 拡張子が .jww でも中身が旧 JWC 形式のファイルが実在する（実装メモ6）')
        return 1
    print('  OK 先頭8バイト = JwwData.')

    try:
        ir = jwwread.read(path)
    except NotImplementedError as ex:
        print(f'  NG 未対応クラス: {ex}')
        return 1
    except Exception as ex:
        print(f'  NG 読み取り中に例外: {type(ex).__name__}: {ex}')
        return 1

    print(f'  OK バージョン {ir["version"]}', end='')
    if ir['version'] not in (700, 230):
        print(' … 未検証のバージョン。結果を必ず図面と突き合わせること')
        ng.append('未検証バージョン')
    else:
        print()

    d, a = ir['declared'], len(ir['entities'])
    if d == a:
        print(f'  OK 宣言要素数 = 読み取り要素数 = {a:,}')
    else:
        print(f'  NG 宣言{d:,} ≠ 実読{a:,}（差 {a - d:+,}）走査がずれている')
        ng.append('要素数不一致')

    if ir.get('header_extra'):
        print(f'  !! ヘッダ終端の想定と {ir["header_extra"]:+,} バイトずれていた'
              f'（走査で補正済み）。未知のヘッダ構成の可能性がある')

    rest = ir['trailing_bytes']
    nblk = len({e['list_no'] for e in ir['entities'] if e['kind'] == 'CDataBlock'})
    nimg = sum(1 for e in ir['entities']
               if e['kind'] == 'CDataMoji' and (e.get('text') or '').startswith('^@BM'))
    if rest in (0, 2, 6):
        print(f'  OK 末尾残 {rest} バイト（ブロック定義・埋め込み画像なしとして説明できる）')
    elif nimg:
        print(f'  OK 末尾残 {rest:,} バイト（埋め込み画像 {nimg} 件の画像データ'
              + (f'＋未対応の CDataList' if nblk else '') + '）')
    elif nblk:
        print(f'  OK 末尾残 {rest:,} バイト（未対応の CDataList。ブロック参照 {nblk} 種）')
    else:
        print(f'  NG 末尾残 {rest:,} バイトが説明できない')
        ng.append('末尾残不明')

    dup = len(ir['entities']) - len(jwwutil.dedupe(ir['entities']))
    if dup:
        print(f'  !! 幾何的に完全一致する重複要素 {dup:,} 件（罠3）'
              f' → jwwutil.dedupe() を通すこと')
    nset = sum(1 for e in ir['entities'] if jwwutil.is_setting_text(e))
    if nset:
        print(f'  !! Jw_cad の設定文字が {nset} 件 図面に入っている（罠9）'
              f' → jwwutil.drop_setting_texts() で落とすこと')
    ov = jwwutil.overlapping_texts(
        jwwutil.drop_setting_texts(jwwutil.dedupe(ir['entities'])))
    if ov:
        print(f'  !! 同一座標に内容の違う文字が重なっている箇所 {len(ov)} 件（罠6）'
              f' → 人間の確認が必要')
        for (g, l, x, y), grp in ov[:5]:
            texts = ' / '.join(sorted({t.get('text') or '' for t in grp}))
            print(f'       ({g},{l}) x={x:.2f} y={y:.2f}  {texts}')
        if len(ov) > 5:
            print(f'       … 他 {len(ov) - 5} 件')

    print('  判定: ' + ('NG（' + '・'.join(ng) + '）' if ng else 'OK'))
    return 1 if ng else 0


def cmd_probe(ir, path, win=None, want=None, all_texts=False):
    """レイヤ割当の調査。**作図系統が変わったら必ず最初にこれを走らせる。**

    レイヤ番号に業界標準は無く、作図者ごとに割当が違う（罠1）。
    部材の意味がレイヤに無く線色や幾何にある系統もあるので、色も出す。
    """
    ents = [e for e in ir['entities'] if _in_win(e, win)]
    print(f'===== {os.path.basename(path)}')
    print(f'  ver{ir["version"]} 要素{len(ir["entities"]):,} '
          f'末尾残{ir["trailing_bytes"]:,}'
          + (f' / 窓内 {len(ents):,}' if win else ''))
    print(f'  公称縮尺 { {k: v for k, v in ir["scale"].items()} }')

    gl = {i: n for i, n in enumerate(ir.get('glayers') or []) if n}
    if gl:
        print(f'  レイヤグループ名 {gl}')
    if ir['layers']:
        print('  レイヤ名:')
        for (g, l), n in sorted(ir['layers'].items()):
            print(f'    ({g},{l}) {n}')
    if not gl and not ir['layers']:
        print('  レイヤ名・レイヤグループ名は取得していない（Ver3.51 未満）')

    print('  (glayer,layer) ごとの内訳:')
    bag = collections.defaultdict(list)
    for e in ents:
        bag[(e['glayer'], e['layer'])].append(e)
    for (g, l), es in sorted(bag.items()):
        cnt = collections.Counter(e['kind'] for e in es)
        kinds = ' '.join(f'{KIND.get(k, k)}{n}' for k, n in cnt.most_common())
        cols = collections.Counter(e['color'] for e in es)
        colstr = ' '.join(f'色{c}:{n}' for c, n in sorted(cols.items()))
        bb = _bbox(es)
        name = ir['layers'].get((g, l), '')
        print(f'    ({g:>2},{l:>2}) {len(es):>7,}  {kinds}')
        print(f'              {colstr}')
        if bb:
            print(f'              x {bb[0]:>10.2f}〜{bb[1]:>10.2f} '
                  f' y {bb[2]:>9.2f}〜{bb[3]:>9.2f}  {name}')

    print('  文字レイヤのサンプル（符号らしい文字列を優先）:')
    for (g, l), es in sorted(bag.items()):
        ts = [e['text'] for e in es
              if e['kind'] == 'CDataMoji' and (e.get('text') or '').strip()
              and not jwwutil.is_setting_text(e)]
        nset = sum(1 for e in es if jwwutil.is_setting_text(e))
        if nset:
            print(f'    ({g},{l}) Jw_cad の設定文字 {nset} 件（罠9。除外した）')
        if not ts:
            continue
        if all_texts or (want and (g, l) == tuple(want)):
            print(f'    ({g},{l}) 全{len(ts):,}件:')
            for t in ts:
                print(f'        {t}')
        else:
            codes = sorted({t for t in ts if CODEISH.match(jwwutil.normalize(t))})
            print(f'    ({g},{l}) {len(ts):,}件  '
                  f'{(codes or sorted(set(ts)))[:12]}')

    print('  図題らしい文字とその座標（面の分け方の手がかり。罠4）:')
    hits = [e for e in ents if e['kind'] == 'CDataMoji'
            and TITLEISH.search(e.get('text') or '')]
    for e in sorted(hits, key=lambda e: (-e['y1'], e['x1']))[:30]:
        print(f'    ({e["glayer"]},{e["layer"]}) '
              f'x={e["x1"]:>9.2f} y={e["y1"]:>9.2f}  {e["text"]}')
    if len(hits) > 30:
        print(f'    … 他 {len(hits) - 30} 件')
    print('  ※ 1ファイルに複数の面が入ることがある。x方向・y方向・図題の位置と')
    print('    分け方は図面ごとに違う（罠4）。1ファイル1面と決め打たないこと。')


def cmd_json(ir, out):
    d = dict(ir)
    d['layers'] = {f'{g},{l}': n for (g, l), n in ir['layers'].items()}
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    print(f'出力: {out}  要素{len(ir["entities"]):,}')


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd, path = argv[0], argv[1]
    rest = [a for a in argv[2:] if not a.startswith('--')]
    opts = [a for a in argv[2:] if a.startswith('--')]

    if cmd == 'verify':
        return cmd_verify(path)

    ir = jwwread.read(path)

    if cmd == 'info':
        cmd_info(ir, path)
    elif cmd == 'probe':
        win = want = None
        for o in opts:
            if o.startswith('--win='):
                win = [float(v) for v in o.split('=', 1)[1].split(',')]
            if o.startswith('--texts='):
                want = [int(v) for v in o.split('=', 1)[1].split(',')]
        cmd_probe(ir, path, win, want, '--all-texts' in opts)
    elif cmd == 'svg':
        import tosvg
        w, h = tosvg.svg(ir, rest[0])
        print(f'出力: {rest[0]}  図面範囲 {w:.1f} x {h:.1f} (図面mm)')
    elif cmd == 'pdf':
        import topdf
        topdf.topdf(ir, rest[0])
        print(f'出力: {rest[0]}')
    elif cmd == 'json':
        cmd_json(ir, rest[0])
    else:
        print(f'未知のサブコマンド: {cmd}')
        print(__doc__)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
