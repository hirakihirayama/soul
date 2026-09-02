# jww-reader

Jw_cad の JWW ファイルを Python で読み取り、PDF / SVG に出力する読み取り専用ツール。

Jw_cad を起動せず、外部変形も使わない。ファイルへの書き込みは一切行わない。

## 動作確認

実案件図面2本（Ver700、32,060 要素 / 8,380 要素）で検証。
リストヘッダが宣言する要素数と、実際に順次走査した要素数が一致し、
末尾6バイト（ブロック定義リストの空カウント + 埋め込み画像数）まで到達。

## 使い方

```bash
pip install reportlab
python3 topdf.py input.jww output.pdf
python3 tosvg.py input.jww output.svg
```

`jwwread.read(path)` は辞書を返す。

```python
{
  'version': 700,
  'zumen': 3,                 # 0-4 = A0-A4
  'layers': {(glayer, layer): 'レイヤ名', ...},
  'declared': 32060,          # ファイルが宣言する要素数
  'entities': [ {...}, ... ],
  'trailing_bytes': 6
}
```

エンティティは以下の形。

```python
{'kind':'CDataSen',  'x1':..,'y1':..,'x2':..,'y2':..,
 'layer':..,'glayer':..,'color':..,'style':..,'flg':..,'group':..}

{'kind':'CDataEnko', 'cx':..,'cy':..,'rad':..,'a0':..,
 'asweep':..,'tilt':..,'flat':..,'full':..}

{'kind':'CDataMoji', 'x1':..,'y1':..,'x2':..,'y2':..,
 'shu':..,'sx':..,'sy':..,'pitch':..,'angle':..,
 'font':'...','text':'...','sunpou_flg':..}
```

## 実装メモ

公式のデータ形式は公開されている。

http://www.jwcad.net/jwdatafmt.txt

全エンティティの `Serialize()` 関数がソースコードのまま載っている。
ただしバイトオフセットの表はないので、自分で積算する必要がある。

以下は、その仕様書だけでは実装できなかった点。

### 1. バージョン番号は 700 で止まっている

`JW_DATA_VERSION` は Ver8 でも Ver10 でも 700。
アプリの版ではなくデータ形式の版であり、7.02 以降は動いていない。

したがってバージョン番号（ファイル先頭）だけで機能の有無を判定する設計にしてはいけない。
クラス名とレコード長で見る。

### 2. MFC の番号表はクラスとオブジェクトで共有されている

JWW は MFC の `CArchive` シリアライズ。タグは以下（MFC TN002）。

- `0xFFFF` + schema(WORD) + namelen(WORD) + クラス名 … クラス初出
- `0x8000 | index` … 既出クラスの参照

この `index` は**クラスとオブジェクトが同じ番号表を共有し、どちらも
1 つずつ消費する**。実測値の例:

```
CDataSen   = 1
CDataEnko  = 28189   (= 1 + 線分 28187 件 + 1)
CDataMoji  = 30964   (= 28189 + 円弧 2774 件 + 1)
```

クラス番号は 1, 2, 3 と続くだろうと決め打つと、2 つ目のクラスで必ず落ちる。
オブジェクトを読んだあとに番号を進めるのを忘れないこと。

### 3. 仕様書に誤記がある

`CDataSen::Serialize` は `m_start.x` を 2 回書いている。

```cpp
ar << (double)m_start.x << (double)m_start.x    // ← 2 番目は m_start.y
   << (double)m_end.x   << (double)m_end.y;
```

実データは正しく double×4（始点 x, y → 終点 x, y）。転記ミスと判断した。

### 4. CData 共通ヘッダは 15 バイト、ただし Ver3.51 未満は 13 バイト

```
DWORD m_lGroup      曲線属性グループ番号   4
BYTE  m_nPenStyle   線種番号               1
WORD  m_nPenColor   線色番号               2
WORD  m_nPenWidth   線幅                   2   ← Ver3.51 未満は存在しない
WORD  m_nLayer      レイヤ番号             2
WORD  m_nGLayer     レイヤグループ番号     2
WORD  m_sFlg        属性フラグ             2
                                        ---- 15
```

古い図面が混在するアーカイブでは、ここを分岐しないと以降のエンティティが
2 バイトずつずれて全て崩れる。

### 5. CDataMoji は線幅の欄に別の値を載せている

仕様書のとおり、`m_nPenWidth` に「寸法値設定フラグ」が入る。
線幅として解釈してはいけない。

本体レイアウト（実測で確認）:

```
double x1, y1, x2, y2       32
DWORD  文字種                4
double sizeX, sizeY          16
double 間隔                   8
double 角度                   8
CString フォント名           可変（長さ 1 byte + 本体）
CString 本文                 可変
```

### 6. 拡張子は信用しない

`.jww` なのに中身が旧 JWC 形式のファイルが実在する。
先頭 8 バイトが `JwwData.` かどうかで判定する。

### 7. 通り芯は範囲を歪める

通り芯は意図的に長く伸ばされることがある。全要素の最小最大で
バウンディングボックスを取ると図面が極端に小さくなる。
`topdf.py` では上下 0.2% を除外している。

## 未対応

`CDataSunpou`（寸法）、`CDataSolid`（塗り）、`CDataTen`（点）、
`CDataBlock`（ブロック参照）、`CDataList`（ブロック定義）は未実装。
検証に使った図面に含まれていなかったため。
遭遇すると `NotImplementedError` を投げる。

なお Jw_cad の寸法コマンドは、既定では線と文字を別々の要素として出力する。
「寸法図形にする」設定を有効にしたときだけ `CDataSunpou` になる。

## IFC 出力について

現時点では実装しない。IFC は「厚さ 150mm の壁、高さ 2.7m」という意味を
要求するが、JWW にあるのは線分と円弧と文字だけ。高さ情報を持たない。

Jw_cad の 2.5D 機能（`m_sFlg & 0x8000` の高さラベル）が使われている図面なら
押し出しは可能だが、検証した図面には 0 件だった。

## ライセンスと利用規約について

Jw_cad の利用規約はプログラム本体の改変および修正版の配布を禁じている。
本コードは Jw_cad 本体に一切触れず、出力された `.jww` ファイルのみを
解析対象とする。

## 参考

- 公式データ形式: http://www.jwcad.net/jwdatafmt.txt
- MFC TN002: https://learn.microsoft.com/en-us/cpp/mfc/tn002-persistent-object-data-format
- JwwExchange（C++ 参考実装 / Unlicense）: https://github.com/JinkiKeikaku/JwwExchange
- 先行記事: https://qiita.com/architectJapan/items/9908ac93f17d2a853855
