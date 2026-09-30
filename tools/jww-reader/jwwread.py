# -*- coding: utf-8 -*-
"""JWW 読み取り（公式仕様書 jwdatafmt.txt + MFC TN002 準拠）

対応クラス: CDataSen / CDataEnko / CDataMoji / CDataSolid / CDataTen /
            CDataSunpou / CDataBlock
未対応:     CDataList（ブロック定義リスト。エンティティリストの後に続くため
            trailing_bytes として残る）。

Ver3.51 未満（実測 Ver230）は CData 共通ヘッダが 13 バイト（末尾の flg が無い）で、
ヘッダ後半のレイアウトも違う。この場合レイヤ名・ペン設定は取得しない。

要素数フィールドは WORD だが、65,535 を超えると MFC の 0xFFFF エスケープ＋DWORD に
なる（Ver230 は件数によらず常にエスケープする）。長さが 2 バイトと 6 バイトで変わる
ため、エンティティリストの先頭は決め打ちせず常に走査で確定する
（_find_entity_list / _entity_count）。想定終端との差は header_extra。

実寸換算: 実寸mm = 格納座標 × そのレイヤグループの縮尺 scale[glayer]
"""
import struct

class R:
    def __init__(s, b): s.b=b; s.p=0
    def dw(s): v=struct.unpack('<I', s.b[s.p:s.p+4])[0]; s.p+=4; return v
    def w(s):  v=struct.unpack('<H', s.b[s.p:s.p+2])[0]; s.p+=2; return v
    def by(s): v=s.b[s.p]; s.p+=1; return v
    def d(s):  v=struct.unpack('<d', s.b[s.p:s.p+8])[0]; s.p+=8; return v
    def st(s):
        """MFC の CString。**Unicode 保存されたファイルがある**(2026-09-30)。

        MFC の長さプレフィクスは `0xFF` の次が `0xFFFE` だと
        「この文字列は Unicode(UTF-16LE)」のマーカーで、**そのあとに長さを読み直す**
        (afx: _AfxReadStringLength)。これを知らないと長さ 0xFFFE = 65,534 と誤読し、
        **ヘッダ終端が数万バイト先へ飛んでエンティティリストを見失う**
        (`エンティティリストの先頭が見つかりません`)。

        実例: ＤＯビル花崎町Ⅵ の意匠図 19点のうち **15点がこれ**だった。
        同じ Ver700・同じ設計事務所でも、ファイルによって ANSI と Unicode が混在する。
        **バージョンでは判別できない。**先頭16バイト目が `FF FE …` なら Unicode。
        """
        n=s.by()
        if n==0xFF:
            n=s.w()
            if n==0xFFFE:          # Unicode(UTF-16LE)。長さを読み直す
                n=s.by()
                if n==0xFF:
                    n=s.w()
                    if n==0xFFFF: n=s.dw()
                v=s.b[s.p:s.p+n*2]; s.p+=n*2
                return v.decode('utf-16-le','replace')
            if n==0xFFFF: n=s.dw()
        v=s.b[s.p:s.p+n]; s.p+=n
        return v.decode('cp932','replace')

CLASSES = ('CDataSen', 'CDataEnko', 'CDataMoji', 'CDataSolid', 'CDataTen',
           'CDataSunpou', 'CDataBlock', 'CDataList')

def _find_entity_list(b, start, ver):
    """エンティティリスト先頭（最初のクラス登録の 0xFFFF）の位置を返す。

    クラス登録は 0xFFFF + スキーマ番号(WORD) + 名前長(WORD) + "CData…" の並び。
    直前の要素数フィールドが 2 バイトか 6 バイトか（エスケープの有無）で位置が
    変わるので、決め打ちせずここで実際の並びから拾う。

    **スキーマ番号はデータ形式のバージョン番号とは別物**で、実測では同じ Ver700
    のファイル間でも値が違った。したがって照合条件には使わず、タグ・名前長・
    既知のクラス名だけで判定する。
    """
    i = start
    while True:
        j = b.find(b'CData', i)
        if j < 0:
            raise ValueError('エンティティリストの先頭が見つかりません')
        k = j - 6
        if k >= start:
            nl  = struct.unpack('<H', b[j-2:j])[0]
            tag = struct.unpack('<H', b[k:k+2])[0]
            if (tag == 0xFFFF and 8 <= nl <= 16
                    and b[j:j+nl].decode('ascii', 'replace') in CLASSES):
                return k
        i = j + 1


def _entity_count(r, p_hdr_end, ver):
    """エンティティリストの要素数を読み、r.p を最初のクラスタグに置く。

    返り値は (要素数, ヘッダ終端との差, スキーマ番号)。差が 0 でなければヘッダの
    レイアウトがこちらの想定と違っていて、走査で補正したということ。
    """
    j = _find_entity_list(r.b, p_hdr_end, ver)
    schema = struct.unpack('<H', r.b[j+2:j+4])[0]
    if struct.unpack('<H', r.b[j-6:j-4])[0] == 0xFFFF:
        # MFC の 0xFFFF エスケープ。要素数が WORD に収まらない（65,535 超）とき、
        # および Ver230 では件数によらず、この形で書かれる
        head = j - 6
        r.p = head + 2
        n = r.dw()
    else:
        head = j - 2
        r.p = head
        n = r.w()
    return n, head - p_hdr_end, schema


def _hdr(r, hdr15=True):
    """CData 共通ヘッダ。Ver3.51 以降は 15 バイト、それ未満は 13 バイト
    （末尾の flg が無い）。入れ子メンバの Serialize もこれを書く"""
    h = {'group':r.dw(), 'style':r.by(), 'color':r.w(), 'width':r.w(),
         'layer':r.w(), 'glayer':r.w()}
    h['flg'] = r.w() if hdr15 else 0
    return h

def _sen(r, hdr15=True):
    h=_hdr(r, hdr15); h['kind']='CDataSen'
    h.update(zip(('x1','y1','x2','y2'), (r.d(),r.d(),r.d(),r.d())))
    return h

def _moji(r, hdr15=True):
    h=_hdr(r, hdr15); h['kind']='CDataMoji'
    h.update(zip(('x1','y1','x2','y2'), (r.d(),r.d(),r.d(),r.d())))
    h['shu']=r.dw(); h['sx']=r.d(); h['sy']=r.d(); h['pitch']=r.d(); h['angle']=r.d()
    h['font']=r.st(); h['text']=r.st()
    h['sunpou_flg']=h['width']
    return h

def _ten(r, hdr15=True):
    h=_hdr(r, hdr15); h['kind']='CDataTen'
    h.update(zip(('x1','y1'), (r.d(),r.d())))
    h['kariten']=r.dw()
    if h['style']==100:
        h['code']=r.dw(); h['angle']=r.d(); h['scale']=r.d()
    return h

def read(path):
    r=R(open(path,'rb').read())
    assert r.b[:8]==b'JwwData.', 'JWWではありません'
    r.p=8
    ver=r.dw(); memo=r.st(); zumen=r.dw(); r.dw()
    scale={}
    for g in range(16):
        r.dw(); r.dw(); scale[g]=r.d(); r.dw()
        for l in range(16): r.dw(); r.dw()
    p_after_scale = r.p   # Ver3.51 未満はここから先のレイアウトが違う
    for _ in range(14): r.dw()
    for _ in range(5):  r.dw()
    r.dw(); r.dw()
    r.d(); r.d(); r.d(); r.dw(); r.dw()
    r.d(); r.d(); r.d(); r.d(); r.d()
    lay={(n,k): r.st() for n in range(16) for k in range(16)}
    glay=[r.st() for _ in range(16)]
    r.d(); r.d(); r.dw(); r.d(); r.d(); r.d(); r.dw()
    r.d(); r.d(); r.d(); r.d(); r.d(); r.d()
    for _ in range(8): r.d(); r.d(); r.d(); r.dw()
    r.d(); r.d(); r.d(); r.dw(); r.d(); r.d(); r.d(); r.dw()
    for _ in range(10): r.d()
    r.d()
    pen_color={}; pen_width={}
    for n in range(10): pen_color[n]=r.dw(); pen_width[n]=r.dw()
    for _ in range(10): r.dw(); r.dw(); r.d()
    for _ in range(8):  [r.dw() for _ in range(4)]
    for _ in range(5):  [r.dw() for _ in range(5)]
    for _ in range(4):  [r.dw() for _ in range(4)]
    for _ in range(3):  r.dw()
    for _ in range(7):  r.dw()
    r.dw(); r.dw(); r.dw(); r.dw(); r.dw(); r.dw()
    r.d(); r.d(); r.d(); r.d(); r.d()
    r.d(); r.d(); r.d(); r.d()
    r.dw(); r.dw()
    for _ in range(257): r.dw(); r.dw()
    for _ in range(257): r.st(); r.dw(); r.dw(); r.d()
    for _ in range(33):  [r.dw() for _ in range(4)]
    for _ in range(33):
        r.st(); r.dw()
        for _ in range(10): r.d()
    for _ in range(10): r.d(); r.d(); r.d(); r.dw()
    r.d(); r.d(); r.d(); r.dw(); r.dw()
    r.d(); r.d(); r.dw()
    for _ in range(6): r.d()

    hdr15 = ver >= 351
    if not hdr15:
        # ヘッダ後半のレイアウトが違う。レイヤ名・ペン設定は捨て、
        # エンティティリストの先頭を走査して確定する
        lay={}; glay=[]; pen_color={}; pen_width={}
        n_declared, hdr_extra, schema = _entity_count(r, p_after_scale, ver)
    else:
        # 要素数は WORD だが 65,535 を超えると 0xFFFF エスケープ＋DWORD になる
        # （実測 159 本のうち 6 本。6万要素超の図面で初めて踏む）。決め打ちで
        # WORD を読むと最初の1件目で走査がずれるので、ここも走査で確定する。
        n_declared, hdr_extra, schema = _entity_count(r, r.p, ver)
    cmap={}; idx=0; ents=[]
    for _ in range(n_declared):
        # MFC TN002: 番号表の index が 0x7FFE を超えると WORD タグが 0x7FFF に
        # 切り替わり、実番号は続く DWORD に入る（クラス参照は 0x80000000 が立つ）。
        # 3万要素を超える図面では必ずここを通る。
        t=r.w()
        if t==0x7FFF:
            dw=r.dw()
            if dw==0xFFFFFFFF:
                r.w(); nl=r.w(); nm=r.b[r.p:r.p+nl].decode(); r.p+=nl
                idx+=1; cmap[idx]=nm; cls=nm
            else:
                cls=cmap[dw & 0x7FFFFFFF]
        elif t==0xFFFF:
            r.w(); nl=r.w(); nm=r.b[r.p:r.p+nl].decode(); r.p+=nl
            idx+=1; cmap[idx]=nm; cls=nm
        else:
            cls=cmap[t & 0x7FFF]
        grp=r.dw(); style=r.by(); col=r.w(); wid=r.w()
        ly=r.w(); gly=r.w(); flg=r.w() if hdr15 else 0
        e={'kind':cls,'layer':ly,'glayer':gly,'color':col,'style':style,'flg':flg,'group':grp}
        if cls=='CDataSen':
            e.update(zip(('x1','y1','x2','y2'), (r.d(),r.d(),r.d(),r.d())))
        elif cls=='CDataEnko':
            e.update(zip(('cx','cy','rad','a0','asweep','tilt','flat'),
                         (r.d(),r.d(),r.d(),r.d(),r.d(),r.d(),r.d())))
            e['full']=r.dw()
        elif cls=='CDataMoji':
            e.update(zip(('x1','y1','x2','y2'), (r.d(),r.d(),r.d(),r.d())))
            e['shu']=r.dw(); e['sx']=r.d(); e['sy']=r.d()
            e['pitch']=r.d(); e['angle']=r.d()
            e['font']=r.st(); e['text']=r.st()
            e['sunpou_flg']=wid   # 仕様書: CDataMojiは線幅欄に寸法値フラグを載せる
        elif cls=='CDataSolid':
            # 4点(double×8)。線色番号10のときのみ RGB(DWORD) が続く
            v=[r.d() for _ in range(8)]
            if col==10: e['rgb']=r.dw()
            if style>=101:
                # 円ソリッド（塗り円・塗り円弧）。4点スロットには頂点ではなく
                # 円弧パラメータが入る。仕様書の対応:
                #   m_start=円心 / m_end.x=半径 m_end.y=扁平率
                #   m_DPoint2.x=傾き角 m_DPoint2.y=開始角
                #   m_DPoint3.x=弧長角 m_DPoint3.y=円弧種別
                # ここを多角形として描くと図面全体に巨大な三角形が走る。
                e['circle']=True
                e['cx'],e['cy'],e['rad'],e['flat']=v[0],v[1],v[2],v[3]
                e['tilt'],e['a0'],e['asweep'],e['ctype']=v[4],v[5],v[6],v[7]
                e['full']=(e['ctype']==-1.0)   # 推定: -1=全円（実測 -1/5/0 のみ出現）
                e['x1'],e['y1']=v[0],v[1]      # 全要素が座標を持つ IR 契約のため
            else:
                e['circle']=False
                e.update(zip(('x1','y1','x2','y2','x3','y3','x4','y4'), v))
        elif cls=='CDataTen':
            # 1点 + 仮点。線種番号100(= m_nCode != 0)のときのみ 種類/回転角/倍率
            e.update(zip(('x1','y1'), (r.d(),r.d())))
            e['kariten']=r.dw()
            if style==100:
                e['code']=r.dw(); e['angle']=r.d(); e['scale']=r.d()
        elif cls=='CDataSunpou':
            # 寸法線 + 寸法値。Ver4.20 以降は SXFモード + 補助線2 + 点2 + 補助点2。
            # 入れ子メンバは各自 CData ヘッダを持つ（クラスタグは持たない）
            e['sen']=_sen(r, hdr15); e['moji']=_moji(r, hdr15)
            e['text']=e['moji'].get('text')
            if ver>=420:
                e['sxf']=r.w()
                e['senho']=[_sen(r, hdr15), _sen(r, hdr15)]
                e['ten']=[_ten(r, hdr15), _ten(r, hdr15)]
                e['tenho']=[_ten(r, hdr15), _ten(r, hdr15)]
            # 全エンティティが座標を持つ IR 契約を保つため寸法線の座標を昇格させる
            for k in ('x1','y1','x2','y2'): e[k]=e['sen'][k]
        elif cls=='CDataBlock':
            # 基準点 + X/Y倍率 + 回転角 + 参照するブロック定義番号
            e.update(zip(('x1','y1','sx','sy','angle'),
                         (r.d(),r.d(),r.d(),r.d(),r.d())))
            e['list_no']=r.dw()
        else:
            raise NotImplementedError(f'未対応クラス: {cls}')
        ents.append(e)
        idx+=1   # MFC: オブジェクトもクラスと同じ番号表を1つ消費する
    rest=len(r.b)-r.p
    return {'version':ver,'zumen':zumen,'memo':memo,'scale':scale,
            'layers':{k:v for k,v in lay.items() if v},'glayers':glay,
            'pen_color':pen_color,'pen_width':pen_width,
            'declared':n_declared,'entities':ents,'trailing_bytes':rest,
            'header_extra':hdr_extra,'schema':schema}
