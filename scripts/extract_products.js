/**
 * 赛狐ERP装箱信息数据提取器 (v1.0)
 *
 * 完全基于 Tampermonkey 脚本 "FBA货件数据提取结果" 的 extractProducts() 逻辑。
 * 通过 Playwright CDP 的 page.evaluate() 注入浏览器运行，只读不写。
 *
 * 用法（Node.js / Playwright）:
 *   const extractFn = fs.readFileSync('scripts/extract_products.js', 'utf-8');
 *   const data = await page.evaluate(`(${extractFn})()`);
 *
 * 返回格式:
 * {
 *   shipmentId: "FBA15G9PQV6M",
 *   warehouseCode: "XJE2",
 *   totalBoxes: 5,
 *   totalProducts: 27,
 *   boxes: [
 *     {
 *       boxNo: "FBA15G9xxxU000001",
 *       boxIndex: 1,
 *       products: [
 *         { img_url, fnsku, productName, sku, quantity, asin, msku, amazonDomain }
 *       ]
 *     }
 *   ],
 *   products: [...]  // 扁平列表，含 boxNo + boxIndex
 * }
 */

(function extractShipmentData() {
  'use strict';

  // ==================== 展开所有折叠的商品 ====================
  var expandBtns = document.querySelectorAll('button');
  expandBtns.forEach(function(btn) {
    var t = (btn.textContent || '').trim();
    if (t.indexOf('展开') !== -1) {
      try { btn.click(); } catch(e) {}
    }
  });

  // ==================== 核心提取逻辑（复制自 Tampermonkey 脚本） ====================

  function extractProducts() {
    var products = [];
    var rows = document.querySelectorAll('.vxe-body--row, .vxe-table--body tbody tr, .el-table__body-wrapper tbody tr, tr');
    var currentBox = '';

    rows.forEach(function(row) {
      var img = row.querySelector('img[src*="images-amazon"], img[src*="ssl-images"], img[src*="amazon"]');

      // 无产品图片 → 可能是箱号行，提取箱号
      if (!img) {
        var boxMatch = (row.textContent || '').match(/FBA[A-Z0-9]{13,}P?\d*/);
        if (boxMatch) currentBox = boxMatch[0];
        return;
      }

      if (!currentBox) return;

      var cells = row.querySelectorAll('td');
      if (cells.length < 5) return;

      var imgSrc = img.src || img.getAttribute('data-src') || '';
      // 将缩略图URL转为原图URL（去掉 _SLxxx_、_AC_USxxx_ 等尺寸后缀）
      imgSrc = imgSrc.replace(/\._(SL|SX|SY|SS|AC_US|US|AC_UL|UL|AC_SX|AC_SY|AC_SS)\d+_\./i, '.');

      var fnsku = '', productName = '', sku = '', quantity = '', asin = '', msku = '', amazonDomain = 'www.amazon.com';
      var vxeCells = row.querySelectorAll('.vxe-cell');

      // 从ASIN列（第二个vxe-cell ci=1）中的Amazon链接提取ASIN和域名
      if (vxeCells.length >= 2) {
        var asinCell = vxeCells[1];
        var asinLink = asinCell.querySelector('a[href*="amazon"]');
        if (asinLink) {
          var href = asinLink.href;
          var dm = href.match(/https?:\/\/([^\/]+)/);
          if (dm) amazonDomain = dm[1];
          var am = href.match(/\/dp\/([A-Z0-9]{10,13})/);
          if (am) asin = am[1];
        }
        if (!asin) {
          var ct = (asinCell.textContent || '').trim();
          var am2 = ct.match(/\b([A-Z0-9]{10})\b/);
          if (am2) asin = am2[1];
        }
        // 提取MSKU：ASIN列中，去掉ASIN文本后剩下的就是MSKU
        if (asin) {
          var fullText = (asinCell.textContent || '').trim();
          var idx = fullText.indexOf(asin);
          if (idx !== -1) {
            msku = fullText.substring(idx + asin.length).trim();
          } else {
            msku = fullText.replace(/https?:\/\/[^\s]+\s*/g, '').trim();
          }
        } else {
          msku = (asinCell.textContent || '').trim();
        }
      }

      vxeCells.forEach(function(cell, ci) {
        var flexDivs = [];
        cell.childNodes.forEach(function(n) {
          if (n.nodeType === 1 && n.classList && n.classList.contains('flex')) flexDivs.push(n);
        });

        if (ci === 2 && flexDivs.length >= 2) {
          fnsku = (flexDivs[1].textContent || '').trim();
        }

        if (ci === 3) {
          if (flexDivs.length >= 2) {
            productName = (flexDivs[0].textContent || '').trim().replace(/\*\d+[^\d]*$/, '').trim();
            sku = (flexDivs[1].textContent || '').trim();
          } else {
            var t = (cell.textContent || '').trim().split('\n').map(function(s) { return s.trim(); }).filter(function(s) { return s; });
            if (t.length >= 2) {
              productName = t[0].replace(/\*\d+[^\d]*$/, '').trim();
              sku = t[t.length - 1];
            } else {
              productName = t[0] ? t[0].replace(/\*\d+\s*$/, '').trim() : '';
            }
          }
        }

        if (ci === 4) {
          var qs = cell.querySelector('.mr_4');
          quantity = qs ? (qs.textContent || '').trim() : ((cell.textContent || '').trim().match(/^(\d+)/) || [])[1] || '';
        }
      });

      // fallback: 如果 vxe-cell 方式失败，尝试从 td 直读
      if (!fnsku && cells[2]) {
        var l2 = (cells[2].textContent || '').split('\n').map(function(s) { return s.trim(); }).filter(function(s) { return s; });
        if (l2.length >= 2) fnsku = l2[l2.length - 1];
      }
      if (!productName && cells[3]) {
        var l3 = (cells[3].textContent || '').split('\n').map(function(s) { return s.trim(); }).filter(function(s) { return s; });
        if (l3.length >= 1) productName = l3[0].replace(/\*\d+[^\d]*$/, '').trim();
        if (l3.length >= 2) sku = l3[l3.length - 1];
      }
      if (!quantity && cells[4]) {
        var m = (cells[4].textContent || '').trim().match(/^(\d+)/);
        quantity = m ? m[1] : '';
      }

      products.push({
        boxNo: currentBox,
        img_url: imgSrc,
        fnsku: fnsku,
        productName: productName,
        sku: sku,
        quantity: parseInt(quantity) || 0,
        asin: asin,
        msku: msku,
        amazonDomain: amazonDomain
      });
    });

    return products;
  }

  // ==================== 提取数据并构建结果 ====================

  var rawProducts = extractProducts();

  // 提取货件ID（从URL或页面文本）
  var shipmentId = '';
  var urlMatch = (location.href || '').match(/amazonShipmentId=(FBA[A-Z0-9]+)/);
  if (urlMatch) {
    shipmentId = urlMatch[1];
  } else {
    var textMatch = (document.body.innerText || '').match(/FBA[A-Z0-9]{10,}/);
    if (textMatch) shipmentId = textMatch[0];
  }

  // 提取物流中心编码（同一页面，不再需要二次CDP查询）
  var warehouseCode = '';
  var wcMatch = (document.body.innerText || '').match(/物流中心编码\s*\n([\w-]+)/);
  if (wcMatch) warehouseCode = wcMatch[1];

  // 按箱号分组，分配箱序号
  var boxMap = {};
  var boxOrder = [];
  rawProducts.forEach(function(p) {
    if (!boxMap[p.boxNo]) {
      boxMap[p.boxNo] = { boxNo: p.boxNo, products: [] };
      boxOrder.push(p.boxNo);
    }
    boxMap[p.boxNo].products.push({
      img_url: p.img_url,
      fnsku: p.fnsku,
      productName: p.productName,
      sku: p.sku,
      quantity: p.quantity,
      asin: p.asin,
      msku: p.msku,
      amazonDomain: p.amazonDomain
    });
  });

  var boxes = boxOrder.map(function(bn, i) {
    var b = boxMap[bn];
    b.boxIndex = i + 1;
    return b;
  });

  // 扁平产品列表（含 boxNo + boxIndex）
  var flatProducts = rawProducts.map(function(p, i) {
    var bi = boxOrder.indexOf(p.boxNo) + 1;
    return {
      boxNo: p.boxNo,
      boxIndex: bi,
      img_url: p.img_url,
      fnsku: p.fnsku,
      productName: p.productName,
      sku: p.sku,
      quantity: p.quantity,
      asin: p.asin,
      msku: p.msku,
      amazonDomain: p.amazonDomain
    };
  });

  return {
    shipmentId: shipmentId,
    warehouseCode: warehouseCode,
    totalBoxes: boxes.length,
    totalProducts: flatProducts.length,
    boxes: boxes,
    products: flatProducts
  };
})();
