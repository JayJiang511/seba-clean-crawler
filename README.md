# Seba Clean Crawler

夜蝴蝶館 / seba.tw 小說 TXT 淨化爬蟲。

這是一個針對 [夜蝴蝶館](https://seba.tw/) 的互動式小說整理工具。  
它可以根據作品關鍵詞搜尋網站分類，讓使用者選擇想下載的作品分類，然後自動抓取文章、合併分頁章節、清理網站雜項，最後輸出乾淨的 TXT 文件。

## 功能特色

- 支持輸入作品關鍵詞搜尋分類
- 支持簡體輸入，例如輸入 `禁咒师` 也能匹配 `禁咒師`
- 支持多選分類，例如一次選擇 `1,2,3` 或 `1-4`
- 支持直接輸入分類網址抓取
- 支持按 URL / 文件名自然排序
- 支持自動合併分頁章節，例如：
  - `第一章（一）`
  - `第一章（二）`
  - `第一章（三）`
- 支持自動提取真正章節標題
- 支持清理網站菜單、分類導航、廣告、贊助文字、上一篇 / 下一篇等雜項
- 支持三種輸出模式：
  - 合併 TXT
  - 分章 TXT 文件夾
  - 合併 TXT + 分章 TXT 文件夾

## 適用場景

適合用於整理夜蝴蝶館上公開可訪問的長篇小說文章，例如：

- 禁咒師
- 司命書
- 妖異奇談抄
- 歿世錄
- 其他夜蝴蝶館分類作品

## 安裝

需要 Python 3.10 或更新版本。

先安裝依賴：

```bash
pip install -r requirements.txt
````

如果沒有 `requirements.txt`，可以手動安裝：

```bash
pip install requests beautifulsoup4 lxml opencc-python-reimplemented
```

其中：

```text
requests                      下載網頁
beautifulsoup4                解析 HTML
lxml                          HTML 解析加速
opencc-python-reimplemented   簡繁轉換，可選但推薦
```

## 使用方法

### 互動式運行

```bash
python seba_crawler.py
```

或者：

```bash
python seba_universal_clean_crawler.py
```

輸入：

```text
1
```

表示只輸出合併 TXT。

輸入：

```text
2
```

表示只輸出分章 TXT 文件夾。

輸入：

```text
3
```

表示兩者都輸出。

## 命令行參數

### `--term`

指定搜索關鍵詞。

```bash
python seba_crawler.py --term 禁咒师
```

或：

```bash
python seba_crawler.py --term 禁咒師
```

腳本會自動搜索分類，然後讓你選擇要下載的分類。

### `--category`

直接指定一個或多個分類網址。

```bash
python seba_crawler.py --category "https://seba.tw/category/fantasy-novel/incantation/incantation-2/"
```

也可以一次指定多個分類網址：

```bash
python seba_crawler.py --category "https://seba.tw/category/fantasy-novel/incantation/incantation-i/" "https://seba.tw/category/fantasy-novel/incantation/incantation-2/"
```

### `--mode`

指定輸出模式。

可用值：

```text
merged   只輸出合併 TXT
split    只輸出分章 TXT 文件夾
both     合併 TXT 和分章 TXT 文件夾都輸出
txt      等同於 merged
folder   等同於 split
```

### `--output`

指定輸出文件名前綴。

```bash
python seba_crawler.py --term 禁咒师 --mode merged --output 禁咒師合集
```

會輸出：

```text
禁咒師合集.txt
```

如果多選分類時使用 `--output`，腳本會自動追加序號和分類名，避免覆蓋文件。


### 直接抓取指定分類

```bash
python seba_crawler.py --category "https://seba.tw/category/fantasy-novel/incantation/incantation-2/"
```

### 直接抓取多個分類

```bash
python seba_crawler.py --category "https://seba.tw/category/fantasy-novel/incantation/incantation-i/" "https://seba.tw/category/fantasy-novel/incantation/incantation-2/"
```


## 章節合併規則

腳本會根據夜蝴蝶館常見的文章格式自動合併章節。

例如網站文章可能是：

```text
禁咒師 第二部第一章（一）
禁咒師 第二部第一章（二）
禁咒師 第二部第一章（三）
```

腳本會把它們合併成同一章。

最終章節標題只從 `第 X 章（一）` 這類頁面的正文開頭提取。

例如正文開頭是：

```text
第一章 啟程前往九天之上
```

則最終標題為：

```text
第一章 啟程前往九天之上
```

如果正文開頭是兩行：

```text
第二章
啟程前往九天之上
```

則會合併為：

```text
第二章 啟程前往九天之上
```

如果正文開頭本身帶有：

```text
第二章 啟程前往九天之上（續）
```

則會保留為：

```text
第二章 啟程前往九天之上（續）
```

後續分頁中的重複章節標題會被刪除，只保留正文。

## 自動清理內容

腳本會嘗試自動刪除以下內容：

```text
夜蝴蝶館
Skip to content
Menu
原文：https://...
---
上一篇
下一篇
Posted in
發佈留言
搜尋
近期文章
近期留言
感謝您
若您願意支持blog的持續營運
歡迎餵食
詳情請見說明
```

運行結束後，腳本會輸出殘留檢查結果，例如：

```text
残留检查：
原文：: 0
https://: 0
---: 0
感謝您: 0
blog: 0
贊助: 0
歡迎餵食: 0
詳情請見說明: 0
```

## 注意事項

本工具僅用於整理公開可訪問網頁文本。
請遵守原網站規則與作品版權，不要高頻請求，不要將整理後的全文內容進行未授權二次分發。

建議僅作個人備份、閱讀排版整理、學習 Python 爬蟲用途。
