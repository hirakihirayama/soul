/**
 * 会計PDF管理 — Google Apps Script
 *
 * Google Drive内のPDF（請求書・領収書など）をGemini APIで解析し、
 * スプレッドシートに一覧・集計するツール。
 *
 * 大量のPDFでもApps Scriptの実行時間制限（6分）を超えないよう、
 * 途中で中断 → 自動再開する設計になっている。
 *
 * 主な仕組み:
 * - LockService による排他制御（重複実行の防止）
 * - 時間ベーストリガーによる中断・自動再開
 * - ScriptProperties による処理状態の保存
 *
 * 【セットアップ】
 * 1. 新しいスプレッドシートを作成する（既存データと混ざらないように）
 * 2. 拡張機能 → Apps Script → このコードを貼り付け
 * 3. 下の CONFIG を自分の環境に合わせて設定する
 *    - GEMINI_API_KEY : Google AI Studio で取得したAPIキー
 *    - ROOT_FOLDER_ID : 解析対象のDriveフォルダID
 * 4. startFullProcess() を実行
 *
 * 【APIキーの取り扱いについて（重要）】
 * APIキーはソースに直接書かず、スクリプトプロパティに保存することを推奨する。
 *   設定 → スクリプトプロパティ で GEMINI_API_KEY を登録し、
 *   getApiKey_() がそれを読み込む。
 * このファイルを共有・公開する際は、キーやフォルダIDを絶対に含めないこと。
 *
 * 【注意】
 * - 実行中は同じ関数を手動で押さないこと
 * - 中断後は自動再開を待つか、メニューから「再開」を選ぶ
 */

// ========== 設定 ==========
const CONFIG = {
  // APIキーはスクリプトプロパティ（GEMINI_API_KEY）に保存することを推奨。
  // どうしても直書きする場合のみ、下の '' を書き換える（公開リポジトリには載せないこと）。
  GEMINI_API_KEY: '',
  GEMINI_MODEL: 'gemini-2.5-flash',
  ROOT_FOLDER_ID: 'YOUR_DRIVE_FOLDER_ID_HERE',  // ← 解析対象フォルダのIDに置き換える
  SHEET_MAIN: 'PDF解析結果',
  SHEET_SUMMARY: '集計',
  SHEET_LOG: '処理ログ',
  WAIT_MS: 2500,
  MAX_RUNTIME_MS: 290000,   // 4分50秒で中断（余裕を持たせる）
  RESUME_DELAY_MIN: 2,      // 中断後2分で再開（重複を避けるため長めに）
  LOCK_TIMEOUT_MS: 5000,    // ロック取得のタイムアウト
  PROP_KEY: 'PROCESS_STATE_V2',
  LOCK_KEY: 'PROCESS_RUNNING',
};

const HEADERS = [
  'No.', 'ファイル名', 'フォルダパス', 'リンク', 'サイズ(KB)',
  '書類種別', '発行元', '宛先', '日付',
  '税抜金額', '消費税', '税込金額',
  '摘要・品目', '複数件?', 'ステータス',
];

// ========== APIキー取得 ==========

/**
 * APIキーを取得する。
 * スクリプトプロパティ GEMINI_API_KEY を優先し、なければ CONFIG.GEMINI_API_KEY を使う。
 */
function getApiKey_() {
  const fromProps = PropertiesService.getScriptProperties().getProperty('GEMINI_API_KEY');
  const key = fromProps || CONFIG.GEMINI_API_KEY;
  if (!key) {
    throw new Error('GEMINI_API_KEY が未設定です。スクリプトプロパティに登録してください。');
  }
  return key;
}

// ========== エントリポイント ==========

function startFullProcess() {
  clearAllTriggers_();

  const props = PropertiesService.getScriptProperties();
  props.deleteProperty(CONFIG.PROP_KEY);
  props.deleteProperty(CONFIG.LOCK_KEY);

  const folder = DriveApp.getFolderById(CONFIG.ROOT_FOLDER_ID);
  const pdfList = [];
  scanFolder_(folder, '', pdfList);

  if (pdfList.length === 0) {
    SpreadsheetApp.getUi().alert('PDFが見つかりませんでした。');
    return;
  }

  initSheet_();

  const state = {
    pdfList: pdfList,
    currentIndex: 0,
    rowCounter: 0,
    totalFiles: pdfList.length,
    startedAt: new Date().toISOString(),
  };
  props.setProperty(CONFIG.PROP_KEY, JSON.stringify(state));

  writeLog_(`処理開始: ${pdfList.length} 件のPDFを検出`);
  processNextBatch_();
}

function resumeProcess() {
  // 手動再開時もトリガーをクリア（二重起動防止）
  clearAllTriggers_();

  const stateJson = PropertiesService.getScriptProperties().getProperty(CONFIG.PROP_KEY);
  if (!stateJson) {
    try {
      SpreadsheetApp.getUi().alert('再開する処理がありません。「最初からやり直す」を実行してください。');
    } catch (e) {}
    return;
  }

  const state = JSON.parse(stateJson);
  writeLog_(`再開: ${state.currentIndex}/${state.totalFiles} 件目から`);
  processNextBatch_();
}

function resetAndRestart() {
  clearAllTriggers_();
  const props = PropertiesService.getScriptProperties();
  props.deleteProperty(CONFIG.PROP_KEY);
  props.deleteProperty(CONFIG.LOCK_KEY);
  startFullProcess();
}

// ========== バッチ処理（排他制御付き） ==========

function processNextBatch_() {
  const props = PropertiesService.getScriptProperties();

  // ===== 排他ロック =====
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(CONFIG.LOCK_TIMEOUT_MS)) {
    writeLog_('⚠️ 別のプロセスが実行中のためスキップ');
    return;  // 別プロセスが走っているので何もしない
  }

  // 二重起動チェック（ロック取得後にも確認）
  const runningFlag = props.getProperty(CONFIG.LOCK_KEY);
  if (runningFlag === 'true') {
    writeLog_('⚠️ 実行フラグが立っているためスキップ（前の処理が実行中）');
    lock.releaseLock();
    return;
  }

  // 実行フラグを立てる
  props.setProperty(CONFIG.LOCK_KEY, 'true');
  lock.releaseLock();
  // ===== ここからメイン処理 =====

  try {
    runBatch_();
  } finally {
    // 必ず実行フラグを下ろす
    props.setProperty(CONFIG.LOCK_KEY, 'false');
  }
}

function runBatch_() {
  const props = PropertiesService.getScriptProperties();
  const stateJson = props.getProperty(CONFIG.PROP_KEY);
  if (!stateJson) return;

  let state = JSON.parse(stateJson);
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(CONFIG.SHEET_MAIN);
  const startTime = Date.now();

  let i = state.currentIndex;
  let rowCounter = state.rowCounter;

  // 完了チェック
  if (i >= state.pdfList.length) {
    writeLog_('既に全件完了しています');
    return;
  }

  while (i < state.pdfList.length) {
    // 時間チェック
    if (Date.now() - startTime > CONFIG.MAX_RUNTIME_MS) {
      state.currentIndex = i;
      state.rowCounter = rowCounter;
      props.setProperty(CONFIG.PROP_KEY, JSON.stringify(state));
      writeLog_(`中断 (${i}/${state.totalFiles}件処理済) — ${CONFIG.RESUME_DELAY_MIN}分後に自動再開`);
      scheduleResume_();
      return;
    }

    const pdf = state.pdfList[i];
    const fileNum = i + 1;

    try {
      const file = DriveApp.getFileById(pdf.id);
      const result = analyzePDF_(file);

      for (let j = 0; j < result.entries.length; j++) {
        rowCounter++;
        const entry = result.entries[j];
        const no = result.entries.length > 1 ? `${fileNum}-${j + 1}` : `${fileNum}`;
        const row = [
          no,
          pdf.name,
          j === 0 ? pdf.path : '',
          '',  // リンクは後でHYPERLINK化
          j === 0 ? pdf.size : '',
          entry.docType,
          entry.issuer,
          entry.recipient,
          entry.date,
          entry.amountExTax,
          entry.tax,
          entry.amountInTax,
          entry.items,
          result.entries.length > 1 ? `${result.entries.length}件` : '',
          'OK',
        ];
        sheet.getRange(rowCounter + 1, 1, 1, HEADERS.length).setValues([row]);
      }

      // リンクをハイパーリンクに（最初の行にだけ）
      if (pdf.url) {
        const linkRow = rowCounter - result.entries.length + 2;
        sheet.getRange(linkRow, 4).setFormula(`=HYPERLINK("${pdf.url}", "開く")`);
      }

    } catch (e) {
      rowCounter++;
      const errRow = [
        fileNum, pdf.name, pdf.path, '', pdf.size,
        '', '', '', '', '', '', '',
        '', '', 'エラー: ' + e.message.substring(0, 200)
      ];
      sheet.getRange(rowCounter + 1, 1, 1, HEADERS.length).setValues([errRow]);
      writeLog_(`エラー [${fileNum}] ${pdf.name}: ${e.message.substring(0, 100)}`);
    }

    i++;

    if (i % 10 === 0) {
      // 進捗ログ + 中間保存
      state.currentIndex = i;
      state.rowCounter = rowCounter;
      props.setProperty(CONFIG.PROP_KEY, JSON.stringify(state));
      writeLog_(`進捗: ${i}/${state.totalFiles} 件処理済`);
    }

    if (i < state.pdfList.length) {
      Utilities.sleep(CONFIG.WAIT_MS);
    }
  }

  // ===== 全件完了 =====
  state.currentIndex = i;
  state.rowCounter = rowCounter;
  state.completedAt = new Date().toISOString();
  props.setProperty(CONFIG.PROP_KEY, JSON.stringify(state));

  clearAllTriggers_();
  writeSummary_(ss, state);
  writeLog_(`✅ 全件完了: ${state.totalFiles} ファイル → ${rowCounter} 行出力`);

  try {
    SpreadsheetApp.getUi().alert(
      '処理完了',
      `${state.totalFiles} 件のPDFを処理し、${rowCounter} 行のデータを出力しました。`,
      SpreadsheetApp.getUi().ButtonSet.OK
    );
  } catch (e) {
    // トリガー実行時はUI操作不可
  }
}

// ========== Gemini API ==========

function analyzePDF_(file) {
  const blob = file.getBlob();
  const bytes = blob.getBytes();
  if (bytes.length > 20 * 1024 * 1024) throw new Error('ファイルサイズが20MB超');

  const base64Data = Utilities.base64Encode(bytes);
  const prompt = `この会計書類（PDF）の内容を解析してください。

【ルール】
- 1つの書類につき1つのJSONオブジェクトを返す
- 複数の書類が含まれる場合はJSON配列で返す
- 常に配列 [{...}] で返す（1件でも配列）
- 情報が読み取れない場合は空文字 "" にする
- JSONのみ返す。説明文やコードフェンスは一切不要

各オブジェクトの形式:
[
  {
    "docType": "書類種別（請求書/領収書/明細書/納品書/通知書/振込依頼書/その他）",
    "issuer": "発行元の会社名・団体名",
    "recipient": "宛先の会社名・施設名",
    "date": "発行日（YYYY/MM/DD形式）",
    "amountExTax": "税抜金額（数字のみ）※不明なら空文字",
    "tax": "消費税額（数字のみ）※不明なら空文字",
    "amountInTax": "税込金額（数字のみ）※税込合計が明記されていればそれを記入。なければ税抜+税で計算",
    "items": "主な摘要・品目（カンマ区切り、最大5つ）"
  }
]`;

  const apiKey = getApiKey_();
  const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/${CONFIG.GEMINI_MODEL}:generateContent?key=${apiKey}`;
  const payload = {
    contents: [{
      parts: [
        { inlineData: { mimeType: 'application/pdf', data: base64Data } },
        { text: prompt }
      ]
    }],
    generationConfig: { temperature: 0.1, maxOutputTokens: 4096 }
  };
  const options = {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };

  let response = UrlFetchApp.fetch(endpoint, options);

  // 429 リトライ（最大2回）
  for (let retry = 0; retry < 2 && response.getResponseCode() === 429; retry++) {
    writeLog_(`⏳ レート制限 — ${15 * (retry + 1)}秒待機してリトライ`);
    Utilities.sleep(15000 * (retry + 1));
    response = UrlFetchApp.fetch(endpoint, options);
  }

  if (response.getResponseCode() !== 200) {
    throw new Error(`API ${response.getResponseCode()}: ${response.getContentText().substring(0, 200)}`);
  }

  return parseGeminiResponse_(response);
}

function parseGeminiResponse_(response) {
  const json = JSON.parse(response.getContentText());
  const rawText = json.candidates?.[0]?.content?.parts?.[0]?.text || '';
  const cleaned = rawText.replace(/```json\s*/gi, '').replace(/```\s*/g, '').trim();

  let entries;
  try {
    const arrayMatch = cleaned.match(/\[[\s\S]*\]/);
    if (arrayMatch) {
      entries = JSON.parse(arrayMatch[0]);
    } else {
      const objMatch = cleaned.match(/\{[\s\S]*\}/);
      if (objMatch) {
        entries = [JSON.parse(objMatch[0])];
      } else {
        throw new Error('JSONが見つかりません');
      }
    }
    if (!Array.isArray(entries)) entries = [entries];
  } catch (e) {
    return {
      entries: [{
        docType: '(解析失敗)', issuer: '', recipient: '', date: '',
        amountExTax: '', tax: '', amountInTax: '',
        items: 'パースエラー: ' + e.message
      }]
    };
  }

  return {
    entries: entries.map(e => ({
      docType: e.docType || '',
      issuer: e.issuer || '',
      recipient: e.recipient || '',
      date: e.date || '',
      amountExTax: e.amountExTax || '',
      tax: e.tax || '',
      amountInTax: e.amountInTax || '',
      items: e.items || '',
    }))
  };
}

// ========== フォルダ走査 ==========

function scanFolder_(folder, path, results) {
  const currentPath = path ? path + ' / ' + folder.getName() : folder.getName();
  const files = folder.getFilesByType(MimeType.PDF);
  while (files.hasNext()) {
    const file = files.next();
    results.push({
      id: file.getId(),
      name: file.getName(),
      path: currentPath,
      url: file.getUrl(),
      size: Math.round(file.getSize() / 1024 * 10) / 10,
    });
  }
  const subFolders = folder.getFolders();
  while (subFolders.hasNext()) {
    scanFolder_(subFolders.next(), currentPath, results);
  }
}

// ========== シート初期化 ==========

function initSheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  let sheet = ss.getSheetByName(CONFIG.SHEET_MAIN);
  if (sheet) { sheet.clear(); } else { sheet = ss.insertSheet(CONFIG.SHEET_MAIN); }
  sheet.getRange(1, 1, 1, HEADERS.length).setValues([HEADERS]);
  sheet.getRange(1, 1, 1, HEADERS.length).setFontWeight('bold').setBackground('#4a86c8').setFontColor('#ffffff');
  sheet.setFrozenRows(1);
  const widths = [50, 180, 250, 80, 70, 80, 180, 180, 100, 100, 80, 100, 300, 60, 120];
  widths.forEach((w, i) => sheet.setColumnWidth(i + 1, w));

  let logSheet = ss.getSheetByName(CONFIG.SHEET_LOG);
  if (logSheet) { logSheet.clear(); } else { logSheet = ss.insertSheet(CONFIG.SHEET_LOG); }
  logSheet.getRange(1, 1, 1, 2).setValues([['日時', 'メッセージ']]);
  logSheet.getRange(1, 1, 1, 2).setFontWeight('bold').setBackground('#666666').setFontColor('#ffffff');
  logSheet.setColumnWidth(1, 180);
  logSheet.setColumnWidth(2, 600);
}

// ========== 集計 ==========

function writeSummary_(ss, state) {
  let sheet = ss.getSheetByName(CONFIG.SHEET_SUMMARY);
  if (sheet) { sheet.clear(); } else { sheet = ss.insertSheet(CONFIG.SHEET_SUMMARY); }

  const mainSheet = ss.getSheetByName(CONFIG.SHEET_MAIN);
  const lastRow = mainSheet.getLastRow();

  const typeCounts = {};
  const issuerCounts = {};
  const recipientCounts = {};

  if (lastRow > 1) {
    const data = mainSheet.getRange(2, 1, lastRow - 1, HEADERS.length).getValues();
    data.forEach(row => {
      const docType = row[5], issuer = row[6], recipient = row[7];
      if (docType) typeCounts[docType] = (typeCounts[docType] || 0) + 1;
      if (issuer) issuerCounts[issuer] = (issuerCounts[issuer] || 0) + 1;
      if (recipient) recipientCounts[recipient] = (recipientCounts[recipient] || 0) + 1;
    });
  }

  const summary = [
    ['会計PDF — 解析レポート', ''],
    ['', ''],
    ['処理日時', Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy/MM/dd HH:mm:ss')],
    ['PDFファイル数', state.totalFiles + ' 件'],
    ['出力行数（展開後）', state.rowCounter + ' 行'],
    ['', ''],
    ['【書類種別の内訳】', '件数'],
  ];
  Object.entries(typeCounts).sort((a, b) => b[1] - a[1]).forEach(([k, v]) => summary.push([k, v]));
  summary.push(['', ''], ['【発行元の内訳（上位20）】', '件数']);
  Object.entries(issuerCounts).sort((a, b) => b[1] - a[1]).slice(0, 20).forEach(([k, v]) => summary.push([k, v]));
  summary.push(['', ''], ['【宛先の内訳】', '件数']);
  Object.entries(recipientCounts).sort((a, b) => b[1] - a[1]).forEach(([k, v]) => summary.push([k, v]));

  sheet.getRange(1, 1, summary.length, 2).setValues(summary);
  sheet.getRange(1, 1).setFontWeight('bold').setFontSize(14);
  sheet.setColumnWidth(1, 350);
  sheet.setColumnWidth(2, 80);
}

// ========== ログ ==========

function writeLog_(message) {
  try {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    let sheet = ss.getSheetByName(CONFIG.SHEET_LOG);
    if (!sheet) {
      sheet = ss.insertSheet(CONFIG.SHEET_LOG);
      sheet.getRange(1, 1, 1, 2).setValues([['日時', 'メッセージ']]);
    }
    const timestamp = Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy/MM/dd HH:mm:ss');
    sheet.appendRow([timestamp, message]);
  } catch (e) {}
  Logger.log(message);
}

// ========== トリガー管理 ==========

function scheduleResume_() {
  clearAllTriggers_();  // 必ず先に全削除
  ScriptApp.newTrigger('resumeProcess')
    .timeBased()
    .after(CONFIG.RESUME_DELAY_MIN * 60 * 1000)
    .create();
}

function clearAllTriggers_() {
  ScriptApp.getProjectTriggers().forEach(trigger => {
    if (trigger.getHandlerFunction() === 'resumeProcess') {
      ScriptApp.deleteTrigger(trigger);
    }
  });
}

// ========== メニュー ==========

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('📄 PDF管理')
    .addItem('🚀 全件処理を開始', 'startFullProcess')
    .addItem('▶️ 中断したところから再開', 'resumeProcess')
    .addSeparator()
    .addItem('🔄 最初からやり直す', 'resetAndRestart')
    .addToUi();
}
