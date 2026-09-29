# -*- coding: utf-8 -*-
"""X 用の 16:9 カード(1200×675 PNG)を HTML から headless Chrome で焼く。色・書体はデザイン規約のみ。"""
import os, subprocess
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'img')
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
CSS = '''
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&family=Inter:wght@400;700&display=swap">
<style>
:root{--brand:#106DB1;--deep:#0B5FA5;--ink:#1C1E21;--muted:#6B7480;--rule:#DDE2E7;--alt:#F4F6F8;--red:#D95A5F}
*{box-sizing:border-box}html,body{margin:0;background:#fff}
.card{width:1200px;height:675px;padding:56px 64px;font-family:"Noto Sans JP","Hiragino Kaku Gothic ProN",sans-serif;color:var(--ink);position:relative;overflow:hidden;font-feature-settings:"palt" 1}
.eyebrow{font-family:Inter,sans-serif;font-size:14px;letter-spacing:.14em;color:var(--muted);text-transform:uppercase;margin:0 0 14px}
h1{font-size:46px;line-height:1.25;margin:0 0 10px;color:var(--deep);font-weight:700;letter-spacing:.01em}
.sub{font-size:19px;color:var(--muted);margin:0}
.foot{position:absolute;left:64px;right:64px;bottom:34px;display:flex;justify-content:space-between;font-size:14px;color:var(--muted);border-top:1px solid var(--rule);padding-top:12px}
.foot b{color:var(--deep);font-weight:700}
.num{font-family:Inter,sans-serif;font-variant-numeric:tabular-nums}
.kpi{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;margin-top:38px}
.kpi div{border:1px solid var(--rule);border-radius:8px;padding:22px 24px}
.kpi dt{font-size:16px;color:var(--muted);margin:0 0 8px}
.kpi dd{margin:0;font-family:Inter,sans-serif;white-space:nowrap;font-size:42px;font-weight:700;color:var(--deep);line-height:1.05;font-variant-numeric:tabular-nums}
.kpi dd span{font-size:20px;color:var(--muted);font-weight:400}
.layers{display:grid;grid-template-columns:1fr 1fr;gap:8px 28px;margin-top:22px}
.layer{display:grid;grid-template-columns:44px 1fr;gap:10px;align-items:baseline;padding:8px 14px;border:1px solid var(--rule);border-radius:8px;font-size:18px}
.layer.h{background:var(--alt)}
.layer .n{font-family:Inter,sans-serif;font-weight:700;color:var(--brand);font-size:26px}
.layer b{display:block}.layer span{font-size:14px;color:var(--muted)}
.pr{list-style:none;padding:0;margin:26px 0 0;counter-reset:p}
.pr li{counter-increment:p;display:grid;grid-template-columns:70px 1fr;gap:14px;align-items:baseline;padding:13px 0;border-bottom:1px solid var(--rule)}
.pr li::before{content:counter(p,decimal-leading-zero);font-family:Inter,sans-serif;font-size:34px;font-weight:700;color:var(--brand)}
.pr b{font-size:26px}.pr span{font-size:16px;color:var(--muted);margin-left:14px}
.ba{display:grid;grid-template-columns:1fr 60px 1fr;gap:16px;align-items:stretch;margin-top:30px}
.ba .col{border:1px solid var(--rule);border-radius:8px;padding:26px 30px}
.ba .col.after{border-color:var(--brand);border-width:2px}
.ba h3{margin:0 0 14px;font-size:24px;color:var(--deep)}
.ba ul{margin:0;padding-left:1.2em;font-size:19px;line-height:1.75}
.ba .arrow{display:flex;align-items:center;justify-content:center;font-size:40px;color:var(--muted)}
</style>'''
FOOT = '<div class="foot"><span><b>平山建設</b> ／ JWW estimating ／ 2026-09</span><span>設計課・積算担当の精査前の一次判定 ／ 公開版</span></div>'

CARDS = {
 '01-title': f'''{CSS}<div class="card">
<p class="eyebrow">Hirayama Construction · Claude + Blender</p>
<h1>AI積算の拾い帳は、<br>データベースである</h1>
<p class="sub">図面から数量までの7つの層。1〜5 は Claude が読み書きするテーブル、6・7 はそこから生成。人が書くのは 2・3 と 6 への所見</p>
<div class="layers">
<div class="layer"><span class="n">1</span><div><b>図面の正規化</b><span>一度だけ読んで SQLite に。以後は SQL で問い合わせる</span></div></div>
<div class="layer h"><span class="n">2</span><div><b>作図者プロファイル</b><span>レイヤ・縮尺・面の並び。コードに書かない</span></div></div>
<div class="layer h"><span class="n">3</span><div><b>諸元(決めごと)</b><span>図面から一意に決まらない値。全項目に出典</span></div></div>
<div class="layer"><span class="n">4</span><div><b>部位×役割の規則表</b><span>定着・継手を表で決める。倍率をコードに書かない</span></div></div>
<div class="layer"><span class="n">5</span><div><b>数量と拾い式</b><span>手写しせず再計算。中間ファイルに出自スタンプ</span></div></div>
<div class="layer h"><span class="n">6</span><div><b>人が見る3つの材料</b><span>拾わなかった表・重ね合わせ図・目視チェック票</span></div></div>
<div class="layer"><span class="n">7</span><div><b>躯体モデル(Blender)</b><span>数量と同じ規則で直方体を置く。3Dは検算</span></div></div>
<div class="layer" style="border-style:dashed"><span class="n">＋</span><div><b>突合表</b><span>行ごとに「突合相手」と「出し方」の列</span></div></div>
</div>{FOOT}</div>''',

 '02-results': f'''{CSS}<div class="card">
<p class="eyebrow">3 weeks · 8 projects · wall-type &amp; frame RC</p>
<h1>図面から機械で拾い、7案件を実績と突き合わせた</h1>
<p class="sub">新築RC造・JWW／ベクタPDF の構造図がある場合。マイナスは図面拾いが実績より少ない</p>
<div class="kpi">
<div><dt>コンクリート(6件)</dt><dd>−0.2 〜 −12.5<span> %</span></dd></div>
<div><dt>型枠(5件)</dt><dd>+1.9 〜 −9.6<span> %</span></dd></div>
<div><dt>鉄筋 部位×径(5件・設計数量比を含む)</dt><dd>−1.7 〜 −7.6<span> %</span></dd></div>
</div>
<div class="kpi" style="margin-top:20px;grid-template-columns:1fr 1fr">
<div><dt>鉄筋 部位×径 ／ 3週間前 → 現在</dt><dd>−12 〜 −29 → −1.7 〜 −7.6<span> %</span></dd></div>
<div><dt>実績に寄せるための補正率</dt><dd>0<span> 個 ／ 積算担当への問い 29 問</span></dd></div>
</div>{FOOT}</div>''',

 '03-principles': f'''{CSS}<div class="card">
<p class="eyebrow">Five rules</p>
<h1>5つの原則</h1>
<ol class="pr">
<li><div><b>図面は一度だけ読む</b><span>正規化して SQL で引く。正本は原図</span></div></li>
<li><div><b>形状は機械、決めごとは人</b><span>人が書く値は1つの JSON に、全項目に出典</span></div></li>
<li><div><b>規則は表に、補正率はコードに書かない</b><span>部位 × 役割 → 素の長さ・定着・継手。割増・定着長は基準どおり</span></div></li>
<li><div><b>実績に寄せる率で埋めない</b><span>残差にはすべて説明を付ける。説明できないものは残差のまま</span></div></li>
<li><div><b>人が見るのは、拾わなかった表</b><span>合計は打ち消し合う。3Dを図面に重ねる</span></div></li>
</ol>{FOOT}</div>''',

 '05-overlay': f'''{CSS}<style>.ov{{display:grid;grid-template-columns:1fr 340px;gap:28px;margin-top:18px;align-items:start}}.ov img{{width:100%;height:400px;object-fit:cover;object-position:50% 58%;border:1px solid var(--rule);border-radius:8px;transform:none}}.ov ul{{margin:0;padding-left:1.2em;font-size:18px;line-height:1.7;color:var(--ink)}}.ov .cap{{font-size:13px;color:var(--muted);margin-top:8px}}</style><div class="card">
<p class="eyebrow">Blender as a check, not a picture</p>
<h1>3Dは絵ではなく検算</h1>
<div class="ov"><div><img src="../../2026-09-sachimachi/img/03-frame-overlay-y1.png" alt="軸組図との重ね合わせ"><div class="cap">軸組図(灰)に、数量と同じ規則で置いた直方体の断面(色)を重ねる。通り芯と SL の登録残差 0 mm(壁式RC 5階の例)</div></div>
<ul><li>数量を出す関数と同じ規則で壁・床板・基礎梁を直方体に</li><li>軸組図・立面・断面・伏図に重ね、残った線を見る</li><li>合計の差率に出ない欠落が見える。壁だけ建物の外へ飛び散っていた、屋上パラペットが丸ごと無かった、階の割当から漏れた壁が237本</li><li>同じ .blend から段階別4Dと IFC へ</li></ul></div>{FOOT}</div>''',

 '04-before-after': f'''{CSS}<div class="card">
<p class="eyebrow">Before / After</p>
<h1>人が打つ拾い帳と、AI が読み書きする拾い帳</h1>
<div class="ba">
<div class="col"><h3>Excel の拾い帳(人が図面を見て打つ)</h3><ul>
<li>人が図面を読んで、部位 × 符号 × 寸法 × 本数を打つ</li><li>3工種が1枚から出る。根拠が1枚にある</li><li>図面は拾うたびに読み直す</li><li>決めごとは拾う人の中にある</li><li>AI が読み書きする入口(スキーマ・版・出典)は、当社の使い方では見つからなかった</li></ul></div>
<div class="arrow">→</div>
<div class="col after"><h3>データベース(7つの層)</h3><ul>
<li>図面を一度だけ SQLite に入れ、SQL で問い合わせる</li><li>形状は機械が拾い、決めごとは人が書く(出典つき)</li><li>規則は部位×役割の表。倍率をコードに書かない</li><li>拾わなかった表と3Dの重ね合わせを人が見る</li><li>同じモデルが施工4Dと IFC へ流れる</li></ul></div>
</div>{FOOT}</div>''',
}

os.makedirs(OUT, exist_ok=True)
for name, html in CARDS.items():
    src = os.path.join(OUT, f'{name}.html')
    open(src, 'w', encoding='utf-8').write('<!doctype html><html lang="ja"><head><meta charset="utf-8"><title>' + name + '</title></head><body>' + html + '</body></html>')
    png = os.path.join(OUT, f'{name}.png')
    subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--window-size=1200,675',
                    '--virtual-time-budget=6000', f'--screenshot={png}', 'file://' + src],
                   check=True, capture_output=True)
    os.remove(src)
    print(name, os.path.getsize(png))
