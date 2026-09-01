---
name: cockpit
description: 自分のClaudeセッションを横断して集計し、状態別カンバン（司令席）のArtifactを更新する。「司令席」「コックピット」「どのセッションが止まってる」「待ちの一覧」「セッション棚卸し」と言われたとき、または朝の点検で使う。
---

# 司令席（Cockpit）

Claudeを開く場所は一つではない。会社の机のMac、自宅のMac、スマホ、ブラウザ——
ローカルの `~/.claude/projects/**` は端末ごとに閉じているため横断できないが、
**クラウドのセッションはアカウント単位なので最初から横断している**。このスキルはそちらを集計する。

目的は稼働状況の可視化ではない。**「どれが自分の返事で止まっているか」を消すこと**。

出てくるのは**このスキルを打った人自身のセッションだけ**（`mine: true`）。
他人の板は見えないし、自分の板も他人には見えない。

## 手順

### 1. セッションを取る

`mcp__Claude_Code_Remote__list_sessions` を `mine: true, limit: 25` で呼ぶ。
`has_more` が真なら、返ってきた `last_id` を `after_id` に渡して次ページへ。

**打ち切りは `updated_at` で判断する。** 古く作られたセッションが最近まで動いていることが
あるため、`created_at` が対象窓（既定30日）より古いページに入っても、そのページの
`updated_at` を必ず見る。窓の内側が1件も無いページに達したら終わり
（2026-09-02: `created_at` だけで打ち切って3件取りこぼした）。

Coworkの常駐セッション（tags に `cowork-dispatch-local` 等）は
`list_sessions` の既定一覧に出るが、タイトルが全部 "Dispatch background conversation" になる。
`Cowork ディスパッチ（常駐）` に読み替える。

### 2. 正規化する

`updated_at` が対象窓の内側のものだけを、次の形にして `sessions.json` に書く。
**リポジトリの中には置かない**（スクラッチパッドに置く）。

```json
{
  "generated_at": "<今のUTC時刻・RFC3339>",
  "window_days": 30,
  "sessions": [
    {
      "id": "session_...",
      "title": "...",
      "bucket": "<status_bucket をそのまま>",
      "origin": "desktop_app|web_claude_ai|android|claude_code_cli|null",
      "kind": "<environment_kind: anthropic_cloud|bridge>",
      "repo": "owner/repo または null",
      "branch": "<external_metadata.current_branches の値 または null>",
      "model": "<session_context.model>",
      "updated_at": "...",
      "status_detail": "<post_turn_summary.status_detail>",
      "needs_action": "<post_turn_summary.needs_action。無ければ空文字>",
      "cost_usd": 0.0,
      "unread": true,
      "error": "<external_metadata.last_init_error.error_kind。無ければ省略>"
    }
  ]
}
```

`needs_action` に**顧客・取引先の個人名が入っていることがある**。
その場合は「先方氏名の確認」のように属性へ言い換えて書く（判断に必要な情報は残す）。
氏名そのものをファイルにも会話にも書かない（社内の機密ルールに合わせる）。

### 3. 組み立てる

`build_cockpit.py` は**このスキルと同じディレクトリ**にある（冒頭に示される
"Base directory for this skill" がその場所）。

```bash
python3 <このスキルのディレクトリ>/build_cockpit.py <sessions.json> -o <out>/cockpit.html
```

列の意味づけと並び順はスクリプト側が持っている。ここで判断を足さない。

### 4. 更新する

**画面は一人に一枚**。毎回新しいURLを作らず、その人の既存の板を上書きする。
URLはこの手順書に書かない——Artifactは作った人の持ち物で、他人のURLには publish できない。
各自の板は**タイトルで見つける**。

1. `Artifact` を `action: "list"`（`scope: "mine"`）で呼ぶ
2. タイトルに「司令席」を含むものがあれば、その `url` を使う。
   publish の前に必ず `action: "read"` で現行版を読む（読んでいない版への上書きは拒否される）。
   `favicon` は渡さない（初版のまま）
3. 無ければ**その人の初回**。`url` を渡さず新規に publish し、
   `title` は「司令席」を含む名前、`favicon` に絵文字を1つ渡す。
   返ってきたURLを会話で伝える（以後はタイトルで見つかる）

`label` には「YYYY-MM-DD 更新（N件）」を入れる。

### 5. 報告する

会話には**「あなた待ち」だけ**を、待たせている順に、番号を振って書く。
各行は「タイトル／何を待っているか／何日」。レビュー待ちは件数だけ。
停止・環境消失があれば「答えても届かないので、必要なら新セッションで」と添える。

画面のURLを1行で示して終える。全件をチャットに並べ直さない——それでは司令席の意味がない。

## 前提と限界

- **claude.ai の通常会話（Code以外）は入らない。** `list_sessions` はCodeセッションの一覧で、
  会話ページ自体も外から読めない（403）。板に載せたい案件は、成果物がプログラムでなくても
  Code側でスレッドを開く（2026-09-02 決定）。手入力での取り込みはしない。
- **他人のセッションは入らない。** `mine: true` は同一アカウント発のものだけ。
  これは意図した設計（2026-09-01 決定）。チームで使っても板は混ざらない。
- **ローカルCLIのセッションは入らない。** 端末内の `~/.claude/projects/**` は横断不可。
  必要になったら各端末から索引JSONを1箇所へ吐かせる層を足す（フェーズ2、未着手）。
- **この画面から指示は送れない（2026-09-02 検証済み・不可）。** クラウドのセッションから
  `ListAgents` を呼ぶと "No reachable agents"、`send_message` 相当のツールも渡されない。
  届くのは**同じ端末上のセッション同士**（受信箱ソケット）だけ。送れる司令席が要るなら
  ローカルに置く必要があり、そのときは横断を失う（その端末の分だけになる）。
  いまは各カードから開いて答える。
