#!/usr/bin/env python3
"""sessions.json -> cockpit.html

Claude セッションの正規化 JSON を受け取り、状態別カンバンの単一 HTML を書き出す。
標準ライブラリのみ。データ取得は行わない（取得は .claude/skills/cockpit/SKILL.md 側の仕事）。

    python3 build_cockpit.py data/sessions.json -o out/cockpit.html

入力の契約は README.md の「データ契約」を参照。
"""

import argparse
import html
import json
import sys
from datetime import datetime, timedelta, timezone

# 列の定義。順序がそのまま画面の左→右になる。
JST = timezone(timedelta(hours=9))

COLUMNS = [
    ("blocked", "あなた待ち", "返事がないと進まない。古いものが上。"),
    ("working", "稼働中", "いま動いている。"),
    ("review", "レビュー待ち", "終わって報告済み。見て閉じる。"),
    ("dead", "停止・環境消失", "再開できない。答えても届かない。"),
]

ORIGIN_JA = {
    "desktop_app": "デスクトップ",
    "web_claude_ai": "ブラウザ",
    "android": "スマホ",
    "ios": "スマホ",
    "claude_code_cli": "ターミナル",
}

ERROR_JA = {
    "environment_deleted": "環境が消えた",
    "computer_unreachable": "端末に到達できず",
    "not_found": "見つからない",
}

BUCKET_MAP = {
    "SESSION_STATUS_BUCKET_BLOCKED": "blocked",
    "SESSION_STATUS_BUCKET_WORKING": "working",
    "SESSION_STATUS_BUCKET_REVIEW_READY": "review",
}


def parse_ts(value):
    """RFC3339 文字列を aware datetime に。壊れていたら None。"""
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def classify(session):
    """列を決める。環境が消えたセッションは、入力待ちでも「停止」に置く。

    答えても届かない相手を「あなた待ち」に並べると、待ち行列が嘘になる。
    """
    if session.get("error"):
        return "dead"
    bucket = session.get("bucket", "")
    return BUCKET_MAP.get(bucket, bucket if bucket in {"blocked", "working", "review", "dead"} else "review")


def days_since(session, now):
    dt = parse_ts(session.get("updated_at"))
    if dt is None:
        return None
    return max(0, (now - dt).days)


def esc(value):
    return html.escape(str(value), quote=True)


def repo_short(session):
    repo = session.get("repo")
    if not repo:
        return "リポジトリなし"
    return repo.split("/")[-1]


def render_card(session, now):
    column = classify(session)
    waited = days_since(session, now)
    ask = (session.get("needs_action") or "").strip()
    detail = (session.get("status_detail") or "").strip()
    note = ask or detail

    badges = []
    if session.get("kind") == "bridge":
        badges.append(("端末常駐", "bridge"))
    origin = session.get("origin")
    if origin:
        badges.append((ORIGIN_JA.get(origin, origin), "origin"))
    if session.get("unread"):
        badges.append(("未読", "unread"))
    err = session.get("error")
    if err:
        badges.append((ERROR_JA.get(err, err), "error"))

    badge_html = "".join(
        f'<span class="badge b-{esc(kind)}">{esc(label)}</span>' for label, kind in badges
    )

    meta = []
    branch = session.get("branch")
    meta.append(f'<span class="repo">{esc(repo_short(session))}</span>')
    if branch and branch not in {"main", "master"}:
        meta.append(f'<span class="branch">{esc(branch)}</span>')
    elif branch:
        meta.append(f'<span class="branch main">{esc(branch)}</span>')
    model = session.get("model")
    if model:
        meta.append(f'<span class="model">{esc(model)}</span>')
    cost = session.get("cost_usd")
    if cost:
        meta.append(f'<span class="cost">${cost:,.2f}</span>')
    # リンクで開けなかったとき、また環境が消えて新セッションを立てるときの手がかり。
    meta.append(f'<span class="sid">{esc(session["id"])}</span>')

    wait_html = ""
    if waited is not None:
        unit = "日" if waited else "日未満"
        # 0日は「1日未満」と読ませる。空の太字だと数字が抜けて見える。
        shown = waited if waited else 1
        wait_html = (
            f'<span class="wait" title="最終更新からの日数">'
            f"<b>{shown}</b>{unit}</span>"
        )

    url = f"https://claude.ai/code/{esc(session['id'])}"
    title = esc(session.get("title") or "（無題）")

    note_html = f'<p class="note">{esc(note)}</p>' if note else ""

    return f"""      <article class="card c-{column}" data-repo="{esc(repo_short(session))}" data-column="{column}">
        <div class="head">
          <h3><a href="{url}">{title}</a></h3>
          {wait_html}
        </div>
        {note_html}
        <div class="badges">{badge_html}</div>
        <div class="meta">{''.join(meta)}</div>
      </article>
"""


def sort_key(column):
    """あなた待ちは古い順（待たせている順）、他は新しい順。"""
    if column == "blocked":
        return lambda s: (parse_ts(s.get("updated_at")) or datetime.max.replace(tzinfo=timezone.utc))
    return lambda s: -(parse_ts(s.get("updated_at")) or datetime.min.replace(tzinfo=timezone.utc)).timestamp()


CSS = """
    :root {
      color-scheme: light;
      --ground: #f1f4f5;
      --surface: #ffffff;
      --surface-sunk: #e8edee;
      --ink: #16202b;
      --ink-soft: #4a5865;
      --ink-faint: #78868f;
      --rule: #d3dbdd;
      --accent: #22456b;
      --accent-soft: #dde5ee;
      --wait: #b26a00;
      --wait-soft: #f6ecd9;
      --live: #2f6b4f;
      --live-soft: #dfeae3;
      --calm: #22456b;
      --gone: #6e7a80;
      --gone-soft: #e5e9ea;
      --shadow: 0 1px 2px rgba(22, 32, 43, .07);
    }
    @media (prefers-color-scheme: dark) {
      :root:not([data-theme="light"]) {
        color-scheme: dark;
        --ground: #10171d;
        --surface: #18222b;
        --surface-sunk: #131b22;
        --ink: #e6ecef;
        --ink-soft: #a8b6bf;
        --ink-faint: #7d8b95;
        --rule: #2a3742;
        --accent: #8fb4d9;
        --accent-soft: #1e2f42;
        --wait: #e0a55c;
        --wait-soft: #3a2c14;
        --live: #79bd9a;
        --live-soft: #1a2f26;
        --calm: #8fb4d9;
        --gone: #8b979e;
        --gone-soft: #222c33;
        --shadow: none;
      }
    }
    :root[data-theme="dark"] {
      color-scheme: dark;
      --ground: #10171d;
      --surface: #18222b;
      --surface-sunk: #131b22;
      --ink: #e6ecef;
      --ink-soft: #a8b6bf;
      --ink-faint: #7d8b95;
      --rule: #2a3742;
      --accent: #8fb4d9;
      --accent-soft: #1e2f42;
      --wait: #e0a55c;
      --wait-soft: #3a2c14;
      --live: #79bd9a;
      --live-soft: #1a2f26;
      --calm: #8fb4d9;
      --gone: #8b979e;
      --gone-soft: #222c33;
      --shadow: none;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      background: var(--ground);
      color: var(--ink);
      font-family: "Zen Kaku Gothic New", "Hiragino Kaku Gothic ProN", "Yu Gothic", system-ui, sans-serif;
      font-size: 14px;
      line-height: 1.65;
      -webkit-font-smoothing: antialiased;
    }

    .sheet {
      max-width: 1600px;
      margin: 0 auto;
      padding: 28px 24px 64px;
      display: flex;
      flex-direction: column;
      gap: 20px;
    }

    header.masthead {
      display: flex;
      flex-wrap: wrap;
      align-items: baseline;
      gap: 8px 20px;
      padding-bottom: 14px;
      border-bottom: 2px solid var(--accent);
    }
    .masthead h1 {
      font-family: "Zen Old Mincho", "Hiragino Mincho ProN", "Yu Mincho", serif;
      font-weight: 600;
      font-size: 27px;
      letter-spacing: .04em;
      margin: 0;
      text-wrap: balance;
    }
    .masthead .stamp {
      font-size: 12px;
      color: var(--ink-faint);
      font-variant-numeric: tabular-nums;
      margin-left: auto;
    }

    .tally {
      display: flex;
      flex-wrap: wrap;
      gap: 10px 28px;
      align-items: baseline;
    }
    .tally .item {
      display: flex;
      align-items: baseline;
      gap: 7px;
      font-size: 12px;
      letter-spacing: .06em;
      color: var(--ink-soft);
    }
    .tally .item b {
      font-family: "Zen Old Mincho", serif;
      font-size: 25px;
      line-height: 1;
      font-variant-numeric: tabular-nums;
      font-weight: 600;
    }
    .tally .t-blocked b { color: var(--wait); }
    .tally .t-working b { color: var(--live); }
    .tally .t-review b { color: var(--calm); }
    .tally .t-dead b { color: var(--gone); }

    .controls {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      padding: 10px 12px;
      background: var(--surface-sunk);
      border: 1px solid var(--rule);
      border-radius: 3px;
    }
    .controls .label {
      font-size: 11px;
      letter-spacing: .1em;
      color: var(--ink-faint);
      margin-right: 2px;
    }
    .chip {
      font: inherit;
      font-size: 12px;
      padding: 3px 11px;
      border: 1px solid var(--rule);
      border-radius: 999px;
      background: var(--surface);
      color: var(--ink-soft);
      cursor: pointer;
    }
    .chip:hover { border-color: var(--accent); color: var(--ink); }
    .chip[aria-pressed="true"] {
      background: var(--accent);
      border-color: var(--accent);
      color: var(--ground);
    }
    .chip:focus-visible { outline: 2px solid var(--wait); outline-offset: 2px; }

    .board {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(272px, 1fr));
      gap: 16px;
      align-items: start;
    }

    section.column { display: flex; flex-direction: column; gap: 10px; min-width: 0; }
    .column > header {
      display: flex;
      align-items: baseline;
      gap: 8px;
      padding-bottom: 7px;
      border-bottom: 1px solid var(--rule);
    }
    .column h2 {
      margin: 0;
      font-size: 13px;
      letter-spacing: .1em;
      font-weight: 600;
    }
    .column .count {
      font-variant-numeric: tabular-nums;
      font-size: 12px;
      color: var(--ink-faint);
    }
    .column .hint {
      margin: 0;
      font-size: 11px;
      color: var(--ink-faint);
      line-height: 1.5;
    }
    .col-blocked h2 { color: var(--wait); }
    .col-working h2 { color: var(--live); }
    .col-dead h2 { color: var(--gone); }

    .card {
      background: var(--surface);
      border: 1px solid var(--rule);
      border-left: 3px solid var(--rule);
      border-radius: 2px;
      padding: 11px 13px 12px;
      display: flex;
      flex-direction: column;
      gap: 7px;
      box-shadow: var(--shadow);
      min-width: 0;
    }
    .c-blocked { border-left-color: var(--wait); background: var(--wait-soft); }
    .c-working { border-left-color: var(--live); }
    .c-review  { border-left-color: var(--accent-soft); }
    .c-dead    { border-left-color: var(--gone); opacity: .82; }

    .card .head { display: flex; gap: 10px; align-items: baseline; }
    .card h3 {
      margin: 0;
      font-size: 14px;
      font-weight: 600;
      line-height: 1.45;
      flex: 1;
      min-width: 0;
      overflow-wrap: anywhere;
    }
    .card h3 a { color: inherit; text-decoration: none; border-bottom: 1px solid transparent; }
    .card h3 a:hover { border-bottom-color: currentColor; }
    .card h3 a:focus-visible { outline: 2px solid var(--wait); outline-offset: 2px; }

    .wait {
      flex: none;
      font-size: 10px;
      color: var(--ink-faint);
      font-variant-numeric: tabular-nums;
      white-space: nowrap;
    }
    .wait b {
      font-family: "Zen Old Mincho", serif;
      font-size: 19px;
      font-weight: 600;
      color: var(--ink-soft);
    }
    .c-blocked .wait b { color: var(--wait); }

    .note {
      margin: 0;
      font-size: 12.5px;
      line-height: 1.6;
      color: var(--ink-soft);
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      max-height: 8.4em;
      overflow-y: auto;
    }
    .c-blocked .note {
      color: var(--ink);
      padding-left: 9px;
      border-left: 2px solid var(--wait);
    }

    .badges { display: flex; flex-wrap: wrap; gap: 5px; }
    .badge {
      font-size: 10px;
      letter-spacing: .05em;
      padding: 1px 7px;
      border-radius: 2px;
      background: var(--surface-sunk);
      color: var(--ink-faint);
      border: 1px solid var(--rule);
    }
    .b-bridge { background: var(--accent-soft); color: var(--accent); border-color: var(--accent-soft); }
    .b-unread { background: var(--wait-soft); color: var(--wait); border-color: var(--wait); }
    .b-error  { background: var(--gone-soft); color: var(--gone); }

    .meta {
      display: flex;
      flex-wrap: wrap;
      gap: 4px 10px;
      font-size: 11px;
      color: var(--ink-faint);
      font-variant-numeric: tabular-nums;
    }
    .meta .repo { color: var(--ink-soft); font-weight: 600; }
    .meta .branch { overflow-wrap: anywhere; }
    .meta .branch.main { color: var(--ink-faint); }
    .meta .cost { margin-left: auto; }
    .meta .sid {
      flex-basis: 100%;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 10px;
      color: var(--ink-faint);
      user-select: all;
      overflow-wrap: anywhere;
    }

    .empty {
      font-size: 12px;
      color: var(--ink-faint);
      padding: 10px 0;
      border: 1px dashed var(--rule);
      border-radius: 2px;
      text-align: center;
    }

    footer.colophon {
      font-size: 11.5px;
      color: var(--ink-faint);
      border-top: 1px solid var(--rule);
      padding-top: 12px;
      line-height: 1.7;
    }
    footer.colophon code {
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 11px;
      background: var(--surface-sunk);
      padding: 1px 5px;
      border-radius: 2px;
    }

    @media (prefers-reduced-motion: reduce) {
      * { transition: none !important; animation: none !important; }
    }
"""

JS = """
    (function () {
      var board = document.getElementById("board");
      var cards = Array.prototype.slice.call(board.querySelectorAll(".card"));
      var repoChips = Array.prototype.slice.call(document.querySelectorAll("[data-filter-repo]"));
      var blockedOnly = document.getElementById("blocked-only");
      var state = { repo: "", blocked: false };

      function apply() {
        cards.forEach(function (card) {
          var okRepo = !state.repo || card.dataset.repo === state.repo;
          var okCol = !state.blocked || card.dataset.column === "blocked";
          card.hidden = !(okRepo && okCol);
        });
        board.querySelectorAll(".column").forEach(function (col) {
          var shown = col.querySelectorAll(".card:not([hidden])").length;
          var counter = col.querySelector(".count");
          if (counter) { counter.textContent = shown; }
          var empty = col.querySelector(".empty");
          if (empty) { empty.hidden = shown > 0; }
        });
      }

      repoChips.forEach(function (chip) {
        chip.addEventListener("click", function () {
          var value = chip.dataset.filterRepo;
          state.repo = state.repo === value ? "" : value;
          repoChips.forEach(function (other) {
            other.setAttribute("aria-pressed", String(other.dataset.filterRepo === state.repo));
          });
          apply();
        });
      });

      if (blockedOnly) {
        blockedOnly.addEventListener("click", function () {
          state.blocked = !state.blocked;
          blockedOnly.setAttribute("aria-pressed", String(state.blocked));
          apply();
        });
      }
    })();
"""


def build(payload, now):
    sessions = payload.get("sessions", [])
    grouped = {key: [] for key, _, _ in COLUMNS}
    for session in sessions:
        grouped[classify(session)].append(session)

    columns_html = []
    for key, label, hint in COLUMNS:
        items = sorted(grouped[key], key=sort_key(key))
        cards = "".join(render_card(item, now) for item in items)
        hidden = "" if not items else " hidden"
        empty = f'      <p class="empty"{hidden}>なし</p>\n'
        columns_html.append(
            f"""    <section class="column col-{key}">
      <header>
        <h2>{esc(label)}</h2><span class="count">{len(items)}</span>
      </header>
      <p class="hint">{esc(hint)}</p>
{cards}{empty}    </section>
"""
        )

    repos = sorted({repo_short(s) for s in sessions})
    chips = "".join(
        f'<button type="button" class="chip" data-filter-repo="{esc(r)}" aria-pressed="false">{esc(r)}</button>'
        for r in repos
    )

    tally = "".join(
        f'<span class="item t-{key}"><b>{len(grouped[key])}</b>{esc(label)}</span>'
        for key, label, _ in COLUMNS
    )

    stamp_text = now.astimezone(JST).strftime("%Y-%m-%d %H:%M JST")

    return f"""<title>Root 司令席</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Zen+Old+Mincho:wght@400;600&family=Zen+Kaku+Gothic+New:wght@400;500;700&display=swap">
<style>{CSS}</style>

<div class="sheet">
  <header class="masthead">
    <h1>Root 司令席</h1>
    <span class="stamp">{esc(stamp_text)} 時点 ／ {len(sessions)}件</span>
  </header>

  <div class="tally">{tally}</div>

  <div class="controls">
    <span class="label">絞り込み</span>
    <button type="button" class="chip" id="blocked-only" aria-pressed="false">あなた待ちだけ</button>
    {chips}
  </div>

  <div class="board" id="board">
{''.join(columns_html)}  </div>

  <footer class="colophon">
    列は状態。数字は最終更新からの経過日数。「あなた待ち」は古い順に並ぶ——待たせている順。<br>
    環境が消えたセッションは入力待ちでも「停止」に置く。答えても届かないため。<br>
    生成: <code>cockpit/build_cockpit.py</code>（hirakihirayama/hci）。この画面は非公開。取引先担当者名を含む場合があるため共有しない。
  </footer>
</div>

<script>{JS}</script>
"""


def main(argv=None):
    parser = argparse.ArgumentParser(description="正規化 sessions.json から司令席 HTML を作る")
    parser.add_argument("input", help="正規化済み sessions.json")
    parser.add_argument("-o", "--output", default="out/cockpit.html", help="出力 HTML（既定: out/cockpit.html）")
    args = parser.parse_args(argv)

    with open(args.input, encoding="utf-8") as fh:
        payload = json.load(fh)

    now = parse_ts(payload.get("generated_at")) or datetime.now(timezone.utc)
    document = build(payload, now)

    import os

    out_dir = os.path.dirname(args.output)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(document)

    counts = {}
    for session in payload.get("sessions", []):
        column = classify(session)
        counts[column] = counts.get(column, 0) + 1
    summary = " / ".join(f"{label} {counts.get(key, 0)}" for key, label, _ in COLUMNS)
    print(f"{args.output} ({summary})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
