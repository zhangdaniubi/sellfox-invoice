# sellfox-invoice

> 赛狐ERP → COMMERCIAL INVOICE 自动化 Skill
>
> 从赛狐ERP FBA货件装箱信息页提取数据，抓取Amazon JP价格，自动生成COMMERCIAL INVOICE Excel。
> 内置**6道核对关卡**，任何一关不过则阻断生成，确保发票数据零差错。

## 快速开始

### 1. 安装

在 WorkBuddy 中搜索并安装 `sellfox-invoice` Skill。

### 2. 配置

```bash
# 复制配置模板
cp config.example.json config.json

# 编辑 config.json，修改为你的路径:
#   paths.template     → 你的发票Excel模板路径
#   paths.output_dir   → 发票输出目录
#   paths.output_suffix → 文件名后缀（如 "-新图大陆-DZ02"）
```

### 3. 启动 Chrome 调试模式

```bash
# Windows: 创建快捷方式，目标填写:
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222

# macOS:
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
```

### 4. 前置准备

在 Chrome 中完成以下操作：
1. 登录 `sellfox.com`
2. 打开目标货件的 **装箱信息** 页面
3. 确保所有产品已展开（"产品" radio + "展开更多商品"）

### 5. 生成发票

在 WorkBuddy 对话中说：

> "帮我从赛狐提取数据生成发票"

Skill 会自动：
1. 提取装箱信息（产品、ASIN、FNSKU、数量、箱号）
2. 抓取 Amazon JP 日元价格
3. 清洗中文品名
4. 翻译英文品名/材质/用途
5. 下载产品图片
6. 填入Excel模板（6道核对校验）

---

## 文件结构

```
sellfox-invoice/
├── config.example.json          # 配置模板 → 复制为 config.json
├── SKILL.md                     # 工作流程文档
├── README.md                    # 本文件
├── scripts/
│   ├── extract_products.js      # 浏览器端VXE-Table数据提取
│   ├── fetch_prices.js          # Amazon价格抓取(CDP)
│   └── fill_invoice.py          # Excel填充 v6 (6道核对)
└── data/
    └── translations.json        # 中→英翻译缓存(预置100+条)
```

## 6道核对关卡

| # | 关卡 | 检查内容 | 失败行为 |
|---|------|---------|---------|
| 1 | 数据完整性 | 输入文件存在 / 字段非空 / QTY>0 | 阻断 |
| 2 | 价格有效性 | ASIN覆盖 / 有货才认价 | 警告 |
| 3 | 清洗结果 | 清洗后非空 / 残留检测 | 阻断 |
| 4 | 翻译完整性 | C/G/H列全非空 | 阻断 |
| 5 | 逐列对比 | 源数据 vs Excel 11列逐一比对 | 阻断 |
| 6 | 最终结构 | 行数/图片数/合并/B2/A8 | 阻断 |

## 模板要求

你的 Excel 模板应满足：
- 23列 (A-W)，数据从**第11行**开始
- B2 (B2:G2合并): AWB运单号
- A8 (A8:L8合并): CONSIGNEE 物流中心编码
- 列映射: A=箱号, B=中文品名, C=英文品名, D=带电/带磁, G=材质, H=用途, J=数量, K=单价, L=总价(公式), M=FNSKU, N=FBA箱号, O=图片, P=亚马逊链接

## 依赖

- **Playwright**: `npm install playwright`
- **openpyxl**: `pip install openpyxl`
- **Chrome**: 需以 `--remote-debugging-port=9222` 启动
- **WorkBuddy**: 运行环境

## 配置选项

| 选项 | 默认 | 说明 |
|------|------|------|
| paths.template | (必填) | 发票Excel模板路径 |
| paths.output_dir | (必填) | 发票输出目录 |
| paths.output_suffix | -新图大陆-DZ02 | 文件名后缀 |
| price.rate | 0.7 | 亚马逊售价 × rate = 发票单价 |
| image.display_size_px | 75 | 图片在Excel中的显示尺寸 |
| amazon.domain | www.amazon.co.jp | 价格抓取站点 |
| chrome.cdp_url | http://127.0.0.1:9222 | Chrome调试端口 |

---

## License

MIT
