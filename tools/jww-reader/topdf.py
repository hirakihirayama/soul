# -*- coding: utf-8 -*-
import math, jwwread
JW={0:'#000000',1:'#0000ff',2:'#000000',3:'#00a000',4:'#00a0a0',
    5:'#ff0000',6:'#a000a0',7:'#808000',8:'#808080',9:'#a0a0a0'}
FONT='HeiseiKakuGo-W5'
canvas=None; HexColor=None; _ready=False

def _reportlab():
    """reportlab を遅延 import する。

    PDF を使わない利用者にモジュール先頭で ImportError を出さないため。
    パーサ本体（jwwread）は標準ライブラリだけで動く。
    """
    global canvas, HexColor, _ready
    if _ready:
        return
    try:
        from reportlab.pdfgen import canvas as _canvas
        from reportlab.lib.colors import HexColor as _HexColor
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    except ImportError:
        raise SystemExit('PDF 出力には reportlab が必要です: pip install reportlab')
    pdfmetrics.registerFont(UnicodeCIDFont(FONT))
    canvas, HexColor, _ready = _canvas, _HexColor, True

def solid_col(e):
    """ソリッドの色。線色番号10のときは COLORREF(0x00BBGGRR) が入っている"""
    if e['color']==10 and 'rgb' in e:
        v=e['rgb']
        return HexColor('#%02x%02x%02x' % (v & 0xFF, (v>>8) & 0xFF, (v>>16) & 0xFF))
    return HexColor(JW.get(e['color'],'#000000'))

def solid_pts(e):
    return [(e['x1'],e['y1']),(e['x2'],e['y2']),(e['x3'],e['y3']),(e['x4'],e['y4'])]

def arc_pts(e, n=48):
    """円ソリッドを塗りポリゴンに離散化する。部分円は中心を含めて扇形にする"""
    sw = 2*math.pi if e.get('full') else e['asweep']
    f  = e['flat'] or 1.0
    t  = e['tilt']
    out=[]
    for i in range(n+1):
        a=e['a0']+sw*i/n
        px=e['rad']*math.cos(a); py=e['rad']*f*math.sin(a)
        out.append((e['cx']+px*math.cos(t)-py*math.sin(t),
                    e['cy']+px*math.sin(t)+py*math.cos(t)))
    if not e.get('full'): out.append((e['cx'],e['cy']))
    return out

def topdf(ir, out, papermm=(420,297)):
    _reportlab()
    E=ir['entities']
    xs=[];ys=[]
    for e in E:
        if e['kind']=='CDataEnko':
            xs+=[e['cx']-e['rad'],e['cx']+e['rad']]; ys+=[e['cy']-e['rad'],e['cy']+e['rad']]
        elif e['kind']=='CDataSen':
            xs+=[e['x1'],e['x2']]; ys+=[e['y1'],e['y2']]
        elif e['kind']=='CDataSolid':
            if e.get('circle'):
                xs+=[e['cx']-e['rad'], e['cx']+e['rad']]
                ys+=[e['cy']-e['rad'], e['cy']+e['rad']]
            else:
                p=solid_pts(e); xs+=[q[0] for q in p]; ys+=[q[1] for q in p]
        else: xs.append(e['x1']); ys.append(e['y1'])
    xs.sort(); ys.sort(); n=len(xs)
    q=lambda a,f: a[min(len(a)-1,max(0,int(f*(len(a)-1))))]
    # 通り芯など意図的に長い線が範囲を歪めるため上下0.2%を除外
    x0,x1,y0,y1=q(xs,.002),q(xs,.998),q(ys,.002),q(ys,.998)
    PT=72/25.4
    pw,ph=papermm[0]*PT, papermm[1]*PT
    m=10*PT
    s=min((pw-2*m)/((x1-x0) or 1), (ph-2*m)/((y1-y0) or 1))
    ox=m+((pw-2*m)-(x1-x0)*s)/2 - x0*s
    oy=m+((ph-2*m)-(y1-y0)*s)/2 - y0*s
    T=lambda x,y:(ox+x*s, oy+y*s)
    c=canvas.Canvas(out, pagesize=(pw,ph))
    c.setLineWidth(0.2)
    # ソリッドは線の下に敷く
    for e in E:
        if e['kind']!='CDataSolid': continue
        c.setFillColor(solid_col(e))
        src = arc_pts(e) if e.get('circle') else solid_pts(e)
        p=c.beginPath(); pts=[T(x,y) for x,y in src]
        p.moveTo(*pts[0])
        for q in pts[1:]: p.lineTo(*q)
        p.close(); c.drawPath(p, stroke=0, fill=1)
    cur=None
    for e in E:
        col=HexColor(JW.get(e['color'],'#000000'))
        if e['kind']=='CDataSen':
            if col!=cur: c.setStrokeColor(col); cur=col
            a=T(e['x1'],e['y1']); b=T(e['x2'],e['y2']); c.line(a[0],a[1],b[0],b[1])
        elif e['kind']=='CDataEnko':
            if col!=cur: c.setStrokeColor(col); cur=col
            r=e['rad']*s; f=e['flat'] or 1.0
            cx,cy=T(e['cx'],e['cy'])
            n=max(12,int(abs(e['asweep'])*24/math.pi)+8)
            a0=e['a0']; sw=2*math.pi if e['full'] else e['asweep']
            p=c.beginPath(); first=True
            for i in range(n+1):
                a=a0+sw*i/n
                px=r*math.cos(a); py=r*f*math.sin(a)
                t=e['tilt']
                qx=px*math.cos(t)-py*math.sin(t); qy=px*math.sin(t)+py*math.cos(t)
                if first: p.moveTo(cx+qx,cy+qy); first=False
                else: p.lineTo(cx+qx,cy+qy)
            c.drawPath(p)
    for e in E:
        if e['kind']!='CDataMoji': continue
        c.setFillColor(HexColor(JW.get(e['color'],'#000000')))
        fs=max(1.0, e['sy']*s)
        x,y=T(e['x1'],e['y1'])
        ang=math.degrees(math.atan2(e['y2']-e['y1'], e['x2']-e['x1']))
        c.saveState(); c.translate(x,y); c.rotate(ang)
        c.setFont(FONT, fs)
        c.drawString(0,0,e['text'])
        c.restoreState()
    c.showPage(); c.save()

if __name__=='__main__':
    import sys
    ir=jwwread.read(sys.argv[1]); topdf(ir, sys.argv[2])
    print('出力:', sys.argv[2])
