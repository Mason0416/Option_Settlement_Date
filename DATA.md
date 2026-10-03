# 選擇權結算日 0DTE — 資料說明（2026-09-23 建立）

## 目錄
- `data/settlement_calendar.csv`：期交所官網 TXO 最後結算日與最後結算價（2002-01 → 2026-09-23，907 筆）。kind: M=月選, W=週三週選, F=週五週選。
- `data/finmind/opt/{YYYY-MM-DD}.parquet`：FinMind TaiwanOptionTick，只保留當天到期序列；含結算日日盤 + 前一晚夜盤（2017-05-15 起）。2017-05-17 → 2026-09-18，544 天。
- `data/finmind/fut/{YYYY-MM}.parquet`：台指期逐筆（排除價差單），欄位 settle_date 標示所屬結算日。
- `data/finmind/taiex5s/{YYYY}.parquet`：加權指數 5 秒，settle_date 標示結算日。
- `data/shioaji/opt/{YYYY-MM-DD}.parquet`：永豐逐筆，含 bid/ask（2023-01-04 起才有值），2023-01 → 2026-09 + 補 FinMind 缺洞的 15 天（2020-05 → 2021-05，無 bid/ask）。
- `data/validation_finmind.csv`：逐日驗證結果。

## 已驗證的事實
- SSP = 13:00(不含)–13:25(含) 指數 + 最後一筆收盤指數 的簡單平均，四捨五入到整數。544/544 天用 5 秒指數重算誤差 ≤0.5，2017 至今規則未變。
- FinMind 選擇權 volume 是 B+S 雙邊加總 → 除以 2 才是口數（與 Shioaji 比對比例 0.4965–0.5000）。
- FinMind 選擇權日盤缺 15 天：2020-05-20, 06-17, 07-22, 07-29, 08-05, 08-12, 08-19, 08-26, 09-02, 09-09, 09-23, 12-23, 2021-01-06, 02-24, 05-05 → 用 Shioaji 成交補。
- Shioaji ts 已是台灣時間（不用 +8）。在 Mac 上拉的檔案只有日盤；在 UTC 機器上拉的含前一晚夜盤。
- Shioaji bid/ask 2022-12-28 以前全為 0，2023-01-04 起有值。
- Shioaji 合約代碼：週三 W1/W2/W4/W5 = TX1/TX2/TX4/TX5，月選 = TXO，週五 F1–F5 = TXU/TXV/TXX/TXY/TXZ；月份碼 Call A–L、Put M–X，最後一碼是年份個位數。

## 樣本切分
- In-sample：2017-05-15 → 2022-12-31（成交價 + 價差模型）
- Out-of-sample：2023-01 → 2026-09（真實 ask）

## 腳本
- `scripts/sj_loop.py`：Shioaji 續拉（每日 500MB 額度，自動等隔天 08:10），可隨時中斷重跑。
- `scripts/fm_pull.py`：FinMind 拉取（可續拉）。
- `_to_delete/`：暫存與舊格式檔，可以整個刪掉。
