---
name: sellfox-invoice
description: 从赛狐ERP (sellfox.com) FBA货件装箱信息页提取数据，抓取Amazon JP价格，自动生成COMMERCIAL INVOICE Excel。内置6道核对关卡确保数据零差错。
agent_created: true
---

# sellfox-invoice

赛狐ERP → COMMERCIAL INVOICE 自动化流水线。通过 Playwright CDP 直连 Chrome 提取赛狐ERP VXE-Table 数据，抓取 Amazon JP 日元价格，清洗翻译后填入 Excel 模板。

## 前置条件

1. **[Chrome 调试模式]**：Chrome 需以 `--remote-debugging-port=9222` 启动
2. **[赛狐登录]**：Chrome 已登录 sellfox.com，FBA 货件**装箱信息**页面已打开
3. **[Playwright]**：`npm install playwright` (在 WorkBuddy 的 Node 环境中)
4. **[openpyxl]**：`pip install openpyxl`
5. **[配置文件]**：首次使用需将 `config.example.json` 复制为 `config.json`，修改路径

## 配置 (config.json)

```json
{
  "paths": {
    "template": "你的发票模板.xlsx",
    "output_dir": "输出目录/",
    "output_suffix": "-新图大陆-DZ02"
  },
  "price": { "rate": 0.7 },
  "image": { "display_size_px": 75, "row_height": 85 },
  "amazon": { "domain": "www.amazon.co.jp" },
  "chrome": { "cdp_url": "http://127.0.0.1:9222" }
}
```

所有路径支持 `~` 表示用户主目录。

## 工作流程

### Step 1: 提取装箱数据

```javascript
const { chromium } = require('playwright');
const fs = require('fs');

// 连接Chrome
const browser = await chromium.connectOverCDP('http://127.0.0.1:9222');
const pages = browser.contexts()[0].pages();
const page = pages.find(p => p.url().includes('sellfox') && p.url().includes('inboundShipment'));

// 注入提取脚本（只读，不修改ERP数据）
const extractFn = fs.readFileSync('scripts/extract_products.js', 'utf-8');
const data = await page.evaluate(extractFn);

// 验证提取完整性
if (!data.shipmentId || data.products.length === 0) {
  throw new Error('提取失败：页面可能未完全加载，请确认已展开所有产品');
}

fs.writeFileSync('shipment_data.json', JSON.stringify(data, null, 2));
```

### Step 2: 抓取Amazon价格

```bash
node scripts/fetch_prices.js shipment_data.json
```

输出 `asin_prices.json`，自动检查库存状态（无货商品K=0）。

**🔴 库存检测**：
- `#availability span` / `#outOfStock` 含「目前无货」→ 价格丢弃
- 仅「现在有货」时接受价格

### Step 3: 下载图片

```bash
python -c "
import json, urllib.request, ssl, os, re
ssl._create_default_https_context = ssl._create_unverified_context
data = json.load(open('shipment_data.json'))
os.makedirs('product_images_full', exist_ok=True)
for i, p in enumerate(data['products']):
    url = re.sub(r'\._[A-Z]{2}\d+_\.', '.', p['img_url'])
    urllib.request.urlretrieve(url, f'product_images_full/img_{i}.jpg')
print(f'Downloaded {len(data[\"products\"])} images')
"
```

### Step 4: 生成发票

```bash
python scripts/fill_invoice.py shipment_data.json asin_prices.json
```

**6道核对关卡**，全部通过才输出最终文件：
1. 数据完整性（文件/字段/QTY）
2. 价格有效性（ASIN覆盖/库存）
3. 清洗结果（非空/残留检测）
4. 翻译完整性（C/G/H全非空→阻断）
5. 逐列对比（11列×N行逐一对照）
6. 最终结构（行数/图片/合并/B2/A8）

## 中文品名清洗规则

共11条规则，严格按顺序执行：

1. 去掉末尾 SKU 编码 (`CKL-XXX` / `DZ02-XXX`)
2. 去掉 emoji (`❗⚠️✅❌⛔🔴🟥`)
3. 去掉包装/价格/操作前缀 (`贵运费-`、`分仓-`、`配飞机盒-` 等)
4. 去掉括号内容 `（...）`
5. 去掉末尾 `+` 后缀
6. 去掉"需要加说明卡"
7. 去掉数量后缀 (`50个装`、`6件套` 等)
8. 去掉 `-NPCS` / `NPCS` 后缀
9. 去掉 `·规格` 后缀
10. 去掉 `*N` 后缀
11. 收尾：多空格→单空格，trim

## 列映射

| 列号 | 字段 | 来源 |
|------|------|------|
| A | 箱序号 | boxIndex |
| B | 中文品名 | ERP name_sku 清洗后 |
| C | 英文品名 | translations.json |
| D | 带电/带磁 | 固定"否" |
| G | 材质(英文) | translations.json |
| H | 用途(英文) | translations.json |
| J | QTY数量 | ERP 实际装箱量 |
| K | UNIT PRICE | Amazon价格 × 0.7 |
| L | TOTAL PRICE | =K*J 公式 |
| M | FNSKU | ERP提取 |
| N | FBA箱号 | box.box_number |
| O | 图片 | 原图嵌入, 75×75居中 |
| P | 亚马逊链接 | https://amazon.co.jp/dp/{ASIN} |

## 安全原则

**本Skill所有操作只读，绝不修改ERP数据。**
翻页和展开按钮是唯一的"点击操作"。

## 故障处理

| 问题 | 处理 |
|------|------|
| CDP连接失败 | Chrome未以调试模式启动 |
| 提取产品数为0 | 确认已展开所有产品，切换到"装箱信息"→"产品" |
| 翻译缺失阻断 | 编辑 `data/translations.json` 补充翻译 |
| 图片下载失败 | 检查URL后缀并重试 |
| 关卡失败 | 查看具体错误信息定位问题 |

## 翻译缓存

`data/translations.json` 是累积的翻译字典，每次生成发票后自动追加新产品。
格式：`{"中文名": ["英文名", "材质", "用途"]}`
