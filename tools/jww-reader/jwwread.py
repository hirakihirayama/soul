# -*- coding: utf-8 -*-
"""JWW 読み取り（公式仕様書 jwdatafmt.txt + MFC TN002 準拠 / 検証範囲: Ver700 の Sen/Enko/Moji）"""
import struct

class R:
    def __init__(s, b): s.b=b; s.p=0
    def dw(s): v=struct.unpack('<I', s.b[s.p:s.p+4])[0]; s.p+=4; return v
    def w(s):  v=struct.unpack('<H', s.b[s.p:s.p+2])[0]; s.p+=2; return v
    def by(s): v=s.b[s.p]; s.p+=1; return v
    def d(s):  v=struct.unpack('<d', s.b[s.p:s.p+8])[0]; s.p+=8; return v
    def st(s):
        n=s.by()
        if n==0xFF:
            n=s.w()
            if n==0xFFFF: n=s.dw()
        v=s.b[s.p:s.p+n]; s.p+=n
        return v.decode('cp932','replace')

def read(path):
    r=R(open(path,'rb').read())
    assert r.b[:8]==b'JwwData.', 'JWWではありません'
    r.p=8
    ver=r.dw(); memo=r.st(); zumen=r.dw(); r.dw()
    scale={}
    for g in range(16):
        r.dw(); r.dw(); scale[g]=r.d(); r.dw()
        for l in range(16): r.dw(); r.dw()
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

    n_declared=r.w()
    cmap={}; idx=0; ents=[]
    for _ in range(n_declared):
        t=r.w()
        if t==0xFFFF:
            r.w(); nl=r.w(); nm=r.b[r.p:r.p+nl].decode(); r.p+=nl
            idx+=1; cmap[idx]=nm; cls=nm
        else:
            cls=cmap[t & 0x7FFF]
        grp=r.dw(); style=r.by(); col=r.w(); wid=r.w()
        ly=r.w(); gly=r.w(); flg=r.w()
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
        else:
            raise NotImplementedError(f'未対応クラス: {cls}')
        ents.append(e)
        idx+=1   # MFC: オブジェクトもクラスと同じ番号表を1つ消費する
    rest=len(r.b)-r.p
    return {'version':ver,'zumen':zumen,'memo':memo,'scale':scale,
            'layers':{k:v for k,v in lay.items() if v},'glayers':glay,
            'pen_color':pen_color,'pen_width':pen_width,
            'declared':n_declared,'entities':ents,'trailing_bytes':rest}
