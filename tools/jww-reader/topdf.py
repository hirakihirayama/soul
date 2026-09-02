# -*- coding: utf-8 -*-
import math, jwwread
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
JW={0:'#000000',1:'#0000ff',2:'#000000',3:'#00a000',4:'#00a0a0',
    5:'#ff0000',6:'#a000a0',7:'#808000',8:'#808080',9:'#a0a0a0'}
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))

def topdf(ir, out, papermm=(420,297)):
    E=ir['entities']
    xs=[];ys=[]
    for e in E:
        if e['kind']=='CDataEnko':
            xs+=[e['cx']-e['rad'],e['cx']+e['rad']]; ys+=[e['cy']-e['rad'],e['cy']+e['rad']]
        elif e['kind']=='CDataSen':
            xs+=[e['x1'],e['x2']]; ys+=[e['y1'],e['y2']]
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
        c.setFont('HeiseiKakuGo-W5', fs)
        c.drawString(0,0,e['text'])
        c.restoreState()
    c.showPage(); c.save()

if __name__=='__main__':
    import sys
    ir=jwwread.read(sys.argv[1]); topdf(ir, sys.argv[2])
    print('出力:', sys.argv[2])
