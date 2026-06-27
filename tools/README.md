# Tools

Human × AI協働のための補助ツール集

## markdown-to-docs.gs

AIが生成したMarkdownテキストをGoogle Docsにコピペしたときに残るアスタリスクや#記号を適切なフォーマットに変換するGoogle Apps Script。

### 対応フォーマット

| Markdown | 変換後 |
|----------|--------|
| `# 見出し` | Heading 1 |
| `## 見出し` | Heading 2 |
| `### 見出し` | Heading 3 |
| `**太字**` | **太字** |

### 使用方法

1. Google Docsを開く
2. 拡張機能 > Apps Script
3. `markdown-to-docs.gs` のコードを貼り付けて保存
4. `convertMarkdownToDocs()` を実行

### 制限事項

- イタリック (`*text*`) は未対応
- リンク (`[text](url)`) は未対応
- リスト (`-`, `1.`) は未対応

拡張が必要な場合はPRをお願いします。

---

## pdf-accounting-manager.gs

Google Drive内のPDF（請求書・領収書・明細書など）を Gemini API で一括解析し、スプレッドシートに一覧・集計するGoogle Apps Script。

大量のPDFでもApps Scriptの実行時間制限（6分）を超えないよう、**途中で中断 → 自動再開**する設計になっている。

### 主な機能

| 機能 | 内容 |
|------|------|
| PDF解析 | Gemini APIで書類種別・発行元・宛先・日付・金額・品目を抽出 |
| 複数書類対応 | 1ファイルに複数書類があれば行を分けて展開 |
| 集計 | 書類種別・発行元・宛先ごとの件数をレポート化 |
| 中断・自動再開 | 実行時間制限の手前で中断し、トリガーで自動再開 |
| 排他制御 | LockService と実行フラグで二重起動を防止 |

### 使用方法

1. 新しいスプレッドシートを作成
2. 拡張機能 > Apps Script
3. `pdf-accounting-manager.gs` のコードを貼り付けて保存
4. APIキーとフォルダIDを設定（下記）
5. メニュー「📄 PDF管理」→「🚀 全件処理を開始」

### 設定（重要）

| 項目 | 設定先 | 説明 |
|------|--------|------|
| `GEMINI_API_KEY` | **スクリプトプロパティ推奨** | [Google AI Studio](https://aistudio.google.com/) で取得 |
| `ROOT_FOLDER_ID` | `CONFIG` | 解析対象のDriveフォルダID |

> **APIキーはソースに直接書かず、スクリプトプロパティ（`GEMINI_API_KEY`）に保存することを推奨します。**
> このファイルを共有・公開する際は、キーやフォルダIDを絶対に含めないでください。

### 制限事項

- 1ファイルあたり20MBまで（Gemini APIの制限）
- 解析精度はGeminiモデルに依存（金額・日付は要確認）
- 出力は人間が確認・補正してから利用する前提

---

*Created with Claude, prompted by Hideki Hirayama (2026-06-27)*
