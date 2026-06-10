#!/usr/bin/env node
/**
 * 赛狐ERP — Amazon JP 价格抓取
 *
 * 通过 Playwright CDP 直连 Chrome，串行抓取每个 ASIN 的日元价格。
 * 内置库存状态检查：无货商品直接跳过（K=0）。
 *
 * 用法:
 *   node scripts/fetch_prices.js <shipment_data.json> [--retries N]
 *
 * 输出: asin_prices.json → 给 fill_invoice.py 使用
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const CDP_URL = 'http://127.0.0.1:9222';
const AMZN_DOMAIN = 'www.amazon.co.jp';

async function main() {
  const args = process.argv.slice(2);
  if (args.length < 1) {
    console.error('用法: node fetch_prices.js <shipment_data.json>');
    process.exit(1);
  }

  const dataPath = args[0];
  if (!fs.existsSync(dataPath)) {
    console.error('数据文件不存在:', dataPath);
    process.exit(1);
  }

  const data = JSON.parse(fs.readFileSync(dataPath, 'utf-8'));
  const asins = [...new Set(data.products.map(p => p.asin))];
  console.log(`ASINs: ${asins.join(', ')} (${asins.length} 个)`);

  let browser;
  try {
    browser = await chromium.connectOverCDP(CDP_URL);
  } catch (e) {
    console.error('CDP连接失败:', e.message);
    console.error('请确保 Chrome 已通过 --remote-debugging-port=9222 启动');
    process.exit(1);
  }

  const ctx = browser.contexts()[0];
  const prices = {};
  const start = Date.now();

  // 串行抓取（保证ASIN-价格精确对应，避免并行错位）
  for (const asin of asins) {
    const page = await ctx.newPage();
    try {
      await page.goto(`https://${AMZN_DOMAIN}/dp/${asin}`, {
        waitUntil: 'domcontentloaded',
        timeout: 15000
      });

      const result = await page.evaluate(() => {
        // 库存状态检查
        const stock = document.querySelector('#availability span, #outOfStock');
        const stockText = stock ? stock.textContent.trim() : '';
        const oos = stockText.includes('目前无货')
                 || stockText.includes('在庫切れ')
                 || stockText.includes('Currently unavailable');

        // 抓取价格（主选择器 + 回退）
        let price = null;
        const mainPrice = document.querySelector('span.a-price span.a-offscreen');
        if (mainPrice) {
          price = mainPrice.textContent.trim();
        } else {
          const fallback = document.querySelector('.a-offscreen');
          if (fallback) price = fallback.textContent.trim();
        }

        return { oos, price, stockText };
      });

      if (result.price && !result.oos) {
        const m = result.price.match(/([¥$€£])\s*([\d,]+\.?\d*)/);
        if (m) {
          prices[asin] = { symbol: m[1], amount: parseFloat(m[2].replace(/,/g, '')) };
          console.log(`  ${asin}: ${m[1]}${m[2]} (有货)`);
        }
      } else if (result.oos) {
        prices[asin] = null;
        console.log(`  ${asin}: 无货 → K=0`);
      } else {
        prices[asin] = null;
        console.log(`  ${asin}: 无价格数据`);
      }
    } catch (e) {
      console.log(`  ${asin}: 错误 - ${e.message}`);
      prices[asin] = null;
    }
    await page.close().catch(() => {});
  }

  const elapsed = ((Date.now() - start) / 1000).toFixed(1);
  console.log(`\n价格抓取完成 (${elapsed}s)`);

  // 写入同目录
  const outDir = path.dirname(dataPath);
  const outPath = path.join(outDir, 'asin_prices.json');
  fs.writeFileSync(outPath, JSON.stringify(prices, null, 2));
  console.log(`已保存: ${outPath}`);
  process.exit(0);
}

main().catch(e => { console.error(e); process.exit(1); });
