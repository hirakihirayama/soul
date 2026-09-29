# 拾い帳は、数字の帳簿から根拠の帳簿へ ─ Claude と Blender の時代の拾い帳(公開版)

3週間で自社8案件の図面(JWW・ベクタPDF・ST-Bridge)から数量を機械で拾い、7案件を実績と突き合わせた到達点と、
そこから見えた「拾い帳はこう変わる」の整理です。2026-09-29 時点。
前の記事「[JWW図面から躯体を立てて、二つの正解に重ねた](../2026-09-sachimachi/)」、
note「[BIMがなくても積算はできました](https://note.com/hidekihirayama/n/nd042cf91a2a5)」の続きにあたります。

| ファイル | 何か |
|---|---|
| [index.html](index.html) | 本文(GitHub Pages)。7つの層・5つの原則・Blender の役割・案件×工種の差率・道具立て |
| [img/05-overlay.png](img/05-overlay.png) | X 用カード: 3Dは絵ではなく検算(軸組図との重ね合わせ) |
| [img/01-title.png](img/01-title.png) | X 用カード: 7つの層 |
| [img/02-results.png](img/02-results.png) | X 用カード: 到達点(差率の幅) |
| [img/03-principles.png](img/03-principles.png) | X 用カード: 5つの原則 |
| [img/04-before-after.png](img/04-before-after.png) | X 用カード: いまの拾い帳と 2026 年の拾い帳 |

## 公開版で除いたもの

案件名・地番・実績数量の絶対値・取引先名(構造事務所・積算事務所・業者)・担当者名。差率と件数だけを載せています。

## この結果の位置づけ

設計課の法規精査・積算担当の確認前の一次判定です。数字は概算であり、建物の性能や適法性を示すものではありません。
JWW の読み取り部分は [tools/jww-reader](https://github.com/hirakihirayama/soul/tree/main/tools/jww-reader)(MIT)。SQL 化・数量・照合・モデル化のツール(116本)は社内リポジトリで育てています。
