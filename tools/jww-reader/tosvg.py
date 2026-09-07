# -*- coding: utf-8 -*-
import math, jwwread
JW = {0:'#000000',1:'#0000ff',2:'#000000',3:'#00a000',4:'#00c0c0',
      5:'#ff0000',6:'#c000c0',7:'#808000',8:'#808080',9:'#a0a0a0'}
def col(n): return JW.get(n, '#000000')

def solid_col(e):
    """ソリッドの色。線色番号10のときは COLORREF(0x00BBGGRR) が入っている"""
    if e['color']==10 and 'rgb' in e:
        v=e['rgb']; return '#%02x%02x%02x' % (v & 0xFF, (v>>8) & 0xFF, (v>>16) & 0xFF)
    return col(e['color'])

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

def svg(ir, out, margin=10):
    xs=[]; ys=[]
    for e in ir['entities']:
        if e['kind']=='CDataSen':
            xs+= [e['x1'],e['x2']]; ys+= [e['y1'],e['y2']]
        elif e['kind']=='CDataEnko':
            xs+= [e['cx']-e['rad'], e['cx']+e['rad']]
            ys+= [e['cy']-e['rad'], e['cy']+e['rad']]
        elif e['kind']=='CDataSolid':
            if e.get('circle'):
                xs+= [e['cx']-e['rad'], e['cx']+e['rad']]
                ys+= [e['cy']-e['rad'], e['cy']+e['rad']]
            else:
                p=solid_pts(e); xs+= [q[0] for q in p]; ys+= [q[1] for q in p]
        else:
            xs.append(e['x1']); ys.append(e['y1'])
    x0,x1=min(xs)-margin, max(xs)+margin
    y0,y1=min(ys)-margin, max(ys)+margin
    W,H = x1-x0, y1-y0
    P=[]
    A=P.append
    A(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.3f} {H:.3f}" width="{W*4:.0f}" height="{H*4:.0f}">')
    A('<rect width="100%" height="100%" fill="#ffffff"/>')
    # JWWはY上向き、SVGはY下向きなので反転
    A(f'<g transform="translate({-x0:.4f},{y1:.4f}) scale(1,-1)" '
      f'stroke-width="0.06" fill="none" vector-effect="non-scaling-stroke">')
    # ソリッドは線の下に敷く
    for e in ir['entities']:
        if e['kind']!='CDataSolid': continue
        if e.get('circle'):
            pts=arc_pts(e)
            d=' '.join(f'{x:.4f},{y:.4f}' for x,y in pts)
            A(f'<polygon points="{d}" fill="{solid_col(e)}" stroke="none"/>')
        else:
            d=' '.join(f'{x:.4f},{y:.4f}' for x,y in solid_pts(e))
            A(f'<polygon points="{d}" fill="{solid_col(e)}" stroke="none"/>')
    for e in ir['entities']:
        c=col(e['color'])
        if e['kind']=='CDataSen':
            A(f'<line x1="{e["x1"]:.4f}" y1="{e["y1"]:.4f}" x2="{e["x2"]:.4f}" y2="{e["y2"]:.4f}" stroke="{c}"/>')
        elif e['kind']=='CDataEnko':
            cx,cy,r=e['cx'],e['cy'],e['rad']; f=e['flat'] or 1.0; t=e['tilt']
            if e['full'] or abs(e['asweep'])>=2*math.pi-1e-9:
                A(f'<ellipse cx="{cx:.4f}" cy="{cy:.4f}" rx="{r:.4f}" ry="{r*f:.4f}" stroke="{c}" '
                  f'transform="rotate({math.degrees(t):.4f} {cx:.4f} {cy:.4f})"/>')
            else:
                a0=e['a0']; a1=a0+e['asweep']
                p0=(cx+r*math.cos(a0)*math.cos(t)-r*f*math.sin(a0)*math.sin(t),
                    cy+r*math.cos(a0)*math.sin(t)+r*f*math.sin(a0)*math.cos(t))
                p1=(cx+r*math.cos(a1)*math.cos(t)-r*f*math.sin(a1)*math.sin(t),
                    cy+r*math.cos(a1)*math.sin(t)+r*f*math.sin(a1)*math.cos(t))
                large=1 if abs(e['asweep'])>math.pi else 0
                sweep=1 if e['asweep']>0 else 0
                A(f'<path d="M {p0[0]:.4f} {p0[1]:.4f} A {r:.4f} {r*f:.4f} '
                  f'{math.degrees(t):.4f} {large} {sweep} {p1[0]:.4f} {p1[1]:.4f}" stroke="{c}"/>')
    A('</g>')
    # 文字は反転させない（別グループ）
    A(f'<g transform="translate({-x0:.4f},{y1:.4f})" stroke="none">')
    for e in ir['entities']:
        if e['kind']!='CDataMoji': continue
        t=(e['text'].replace('&','&amp;').replace('<','&lt;').replace('>','&gt;'))
        ang=-math.degrees(math.atan2(e['y2']-e['y1'], e['x2']-e['x1']))
        A(f'<text x="{e["x1"]:.4f}" y="{-e["y1"]:.4f}" font-size="{e["sy"]:.4f}" '
          f'font-family="sans-serif" fill="{col(e["color"])}" '
          f'transform="rotate({ang:.4f} {e["x1"]:.4f} {-e["y1"]:.4f})">{t}</text>')
    A('</g></svg>')
    open(out,'w',encoding='utf-8').write('\n'.join(P))
    return W,H

if __name__=='__main__':
    import sys
    ir=jwwread.read(sys.argv[1])
    W,H=svg(ir, sys.argv[2])
    print(f'出力 {sys.argv[2]}  図面範囲 {W:.1f} x {H:.1f} (図面mm)')
