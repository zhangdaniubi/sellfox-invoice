#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
赛狐ERP → COMMERCIAL INVOICE (便携版)
GitHub: https://github.com/your-org/sellfox-invoice

6道核对关卡，任何一关不过则阻断生成。
路径通过 config.json 配置，支持跨机器使用。

用法:
  python scripts/fill_invoice.py <shipment_data.json> <asin_prices.json>
"""

import json, os, re, shutil, sys, glob

# ========== 路径解析 ==========
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(SKILL_DIR, 'data')

def resolve_path(p):
    """解析路径: ~/xxx → C:/Users/xxx 等"""
    if p.startswith('~'):
        return os.path.expanduser(p.replace('~', '~'))
    return p

def load_config():
    """加载配置, 优先 config.json, 回退 config.example.json"""
    for name in ['config.json', 'config.example.json']:
        cfg_path = os.path.join(SKILL_DIR, name)
        if os.path.exists(cfg_path):
            with open(cfg_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    raise FileNotFoundError(f'配置文件不存在，请将 config.example.json 复制为 config.json 并修改路径')

CFG = load_config()
TEMPLATE = resolve_path(CFG['paths']['template'])
OUTPUT_DIR = resolve_path(CFG['paths']['output_dir'])
OUTPUT_SUFFIX = CFG['paths'].get('output_suffix', '')
PRICE_RATE = CFG['price']['rate']
START_ROW = 11

# ========== 工具函数 ==========
errors = []
warnings = []

def block(msg):
    errors.append(f'[阻断] {msg}')
    print(f'  ❌ {msg}')

def warn(msg):
    warnings.append(f'[警告] {msg}')
    print(f'  ⚠️ {msg}')

def ok(msg):
    print(f'  ✅ {msg}')

# ========== 中文品名清洗 ==========
def clean_chinese_name(name):
    # 1. 去掉末尾 SKU 编码
    name = re.sub(r'\s*(CKL-\d+|DZ02-\d+)\s*$', '', name)
    # 2. 去掉 emoji
    name = re.sub(r'[❗⚠️✅❌⛔🔴🟥]+', '', name)
    # 3. 去掉包装/价格/操作前缀
    name = re.sub(r'^(需要优化运费·|使用盒装-|优化包装-|贵运费-|分仓-|到亚马逊仓重新测量，需要优化包装--|N\.用盒子包装后重新测量亚马逊运费[^·]*·?|提价\d+\.\d+看效果-|不做-|配飞机盒-|提价-)', '', name)
    name = re.sub(r'^分仓-\s*', '', name)
    # 8. 去掉括号内容
    name = re.sub(r'\s*[（(][^）)]*[）)]\s*$', '', name)
    # 7. 去掉末尾 + 后缀
    name = re.sub(r'\s*\d+\s*个\+.*$', '', name)
    name = re.sub(r'\s*\+.*$', '', name)
    # 4b-0. 去掉"需要加说明卡"
    name = re.sub(r'\s*需要加说明卡\s*$', '', name)
    # 4. 去掉数量后缀
    name = re.sub(r'\s*\d+\s*[片个卷套件只卷条张包盒袋瓶双副套]\s*装.*$', '', name)
    name = re.sub(r'\s*\d+\s*件\s*套\s*$', '', name)
    # 4b. 去掉 -NPCS / NPCS
    name = re.sub(r'\s*-\s*\d+\s*PCS?\s*$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*\d+\s*PCS?\s*$', '', name, flags=re.IGNORECASE)
    # 5. 去掉·规格后缀
    name = re.sub(r'·[^·\s]+$', '', name)
    # 6. 去掉 *N 后缀
    name = re.sub(r'\s*\d*\*\d+\s*$', '', name)
    # 9. 收尾
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def main(shipment_json, prices_json):
    global errors, warnings
    errors = []; warnings = []

    # ========== 关卡1: 数据完整性 ==========
    print('=' * 60)
    print('【关卡1】数据完整性校验')
    print('=' * 60)

    for fpath, label in [(shipment_json, '提取数据'), (prices_json, '价格数据')]:
        if not os.path.exists(fpath):
            block(f'{label} 文件不存在: {fpath}')
        else:
            ok(f'{label} 文件存在 ({os.path.getsize(fpath):,} bytes)')

    trans_path = os.path.join(DATA_DIR, 'translations.json')
    if not os.path.exists(trans_path):
        block(f'翻译缓存不存在: {trans_path}')
    else:
        ok(f'翻译缓存存在 ({os.path.getsize(trans_path):,} bytes)')

    if not os.path.exists(TEMPLATE):
        block(f'模板文件不存在: {TEMPLATE}')
    else:
        ok(f'模板文件存在')

    if errors: sys.exit(1)

    try:
        with open(shipment_json, 'r', encoding='utf-8') as f:
            data = json.load(f)
        with open(prices_json, 'r', encoding='utf-8') as f:
            prices = json.load(f)
        with open(trans_path, 'r', encoding='utf-8') as f:
            TRANSLATION_DICT = json.load(f)
    except json.JSONDecodeError as e:
        block(f'JSON 解析失败: {e}')
        sys.exit(1)

    products = data.get('products', [])
    shipment_id = data.get('shipmentId', '')
    warehouse_code = data.get('warehouseCode', '')
    total_boxes = data.get('totalBoxes', 0)
    total_products = data.get('totalProducts', 0)

    if not shipment_id:      block('shipmentId 为空')
    if not warehouse_code:    block('warehouseCode 为空')
    if len(products) == 0:    block('products 列表为空')
    if total_products != len(products):
        warn(f'totalProducts({total_products}) ≠ 实际({len(products)})')
    else:
        ok(f'产品数一致: {total_products}')

    REQUIRED_FIELDS = ['asin', 'productName', 'fnsku', 'boxNo', 'boxIndex', 'quantity']
    for i, p in enumerate(products):
        for field in REQUIRED_FIELDS:
            if field not in p or p[field] is None or (isinstance(p[field], str) and p[field].strip() == ''):
                block(f'产品 #{i+1} 缺少 "{field}"')
        qty = p.get('quantity', 0)
        if qty is None or qty <= 0:
            block(f'产品 #{i+1} ({p.get("productName","?")[:20]}) 数量异常: {qty}')
        asin = p.get('asin', '')
        if asin and not re.match(r'^B0[A-Z0-9]{8}$', asin):
            warn(f'产品 #{i+1} ASIN格式异常: "{asin}"')

    if not errors:
        ok(f'所有 {len(products)} 个产品必需字段完整')
        ok('所有产品数量 > 0')

    print(f'\n  货件: {shipment_id} | 箱: {total_boxes} | 品: {len(products)} | 仓: {warehouse_code}')
    if errors: sys.exit(1)

    # ========== 关卡2: 价格有效性 ==========
    print('\n' + '=' * 60)
    print('【关卡2】价格有效性校验')
    print('=' * 60)

    distinct_asins = sorted(set(p['asin'] for p in products))
    price_asins = set(prices.keys())
    missing_prices = [a for a in distinct_asins if a not in price_asins]

    for asin in distinct_asins:
        if asin in missing_prices:
            warn(f'{asin}: 无价格数据，K=0')
        else:
            pi = prices[asin]
            if pi is None:
                warn(f'{asin}: 价格为空(可能无货)，K=0')
            elif isinstance(pi, dict) and pi.get('amount'):
                ok(f'{asin}: ¥{pi["amount"]} → K={round(pi["amount"] * PRICE_RATE, 2)}')
            else:
                warn(f'{asin}: 价格数据结构异常: {pi}')

    extra = price_asins - set(distinct_asins)
    if extra: warn(f'多余价格数据: {extra}')
    ok(f'价格覆盖: {len(distinct_asins) - len(missing_prices)}/{len(distinct_asins)} ASIN')

    # ========== 关卡3: 清洗结果 ==========
    print('\n' + '=' * 60)
    print('【关卡3】中文名清洗校验')
    print('=' * 60)

    for p in products:
        original = p['productName']
        cleaned = clean_chinese_name(original)
        if not cleaned:
            block(f'清洗后名称为空: "{original}"')
        residual = []
        if re.search(r'\d+\s*PCS', cleaned, re.IGNORECASE): residual.append('PCS残留')
        if re.search(r'\d+\s*[片个卷套件只]\s*装', cleaned): residual.append('数量后缀残留')
        if re.search(r'\d+\s*件\s*套', cleaned): residual.append('件套残留')
        if re.search(r'[（(]', cleaned): residual.append('括号残留')
        if residual:
            warn(f'可能清洗不完整: "{cleaned}" — {", ".join(residual)}')
        p['name_cn'] = cleaned

    if not errors:
        ok(f'所有 {len(products)} 个产品名清洗完成且非空')

    # ========== 关卡4: 翻译完整性 ==========
    print('\n' + '=' * 60)
    print('【关卡4】翻译完整性校验')
    print('=' * 60)

    missing_trans = []
    for p in products:
        cn = p['name_cn']
        trans = TRANSLATION_DICT.get(cn)
        if trans and trans[0] and trans[1] and trans[2]:
            p['name_en'] = trans[0]
            p['material'] = trans[1]
            p['usage'] = trans[2]
        else:
            missing_trans.append(cn)
            p['name_en'] = trans[0] if trans else ''
            p['material'] = trans[1] if trans and len(trans) > 1 else ''
            p['usage'] = trans[2] if trans and len(trans) > 2 else ''

    if missing_trans:
        for cn in missing_trans:
            block(f'缺少翻译: "{cn}" → C/G/H 列将为空')
        print(f'\n⛔ 关卡4失败: {len(missing_trans)} 个产品缺少翻译')
        print('  请补充翻译到 data/translations.json 后重试')
        sys.exit(1)
    else:
        ok(f'所有 {len(products)} 个产品翻译完整')

    # ========== 组装数据 ==========
    for p in products:
        pi = prices.get(p['asin'])
        if pi and isinstance(pi, dict) and pi.get('amount'):
            p['price_jpy'] = round(pi['amount'] * PRICE_RATE, 2)
        else:
            p['price_jpy'] = 0
        p['qty'] = p['quantity']
        p['amazon_link'] = f'https://{CFG["amazon"]["domain"]}/dp/{p["asin"]}'

    # ========== 填写 Excel ==========
    print('\n' + '=' * 60)
    print('【填表】写入 Excel')
    print('=' * 60)

    from openpyxl import load_workbook
    from openpyxl.drawing.image import Image as XLImage
    from openpyxl.drawing.spreadsheet_drawing import AnchorMarker, OneCellAnchor
    from openpyxl.drawing.xdr import XDRPositiveSize2D
    from openpyxl.utils.units import pixels_to_EMU
    from openpyxl.styles import Alignment

    wb = load_workbook(TEMPLATE)
    ws = wb.active

    merged_ranges = list(ws.merged_cells.ranges)
    for mr in merged_ranges:
        if mr.min_row >= START_ROW:
            ws.unmerge_cells(str(mr))

    ws['B2'] = shipment_id
    ws['A8'] = warehouse_code
    ok(f'B2 AWB = {shipment_id}')
    ok(f'A8 CONSIGNEE = {warehouse_code}')

    for i, p in enumerate(products):
        row = START_ROW + i
        ws.cell(row, 1).value = str(p['boxIndex'])
        ws.cell(row, 2).value = p['name_cn']
        ws.cell(row, 3).value = p['name_en']
        ws.cell(row, 4).value = '否'
        ws.cell(row, 7).value = p['material']
        ws.cell(row, 8).value = p['usage']
        ws.cell(row, 10).value = p['qty']
        ws.cell(row, 11).value = p['price_jpy']
        ws.cell(row, 12).value = f'=K{row}*J{row}'
        ws.cell(row, 13).value = p['fnsku']
        ws.cell(row, 14).value = re.sub(r'P\d+$', '', p['boxNo'])
        ws.cell(row, 16).value = p['amazon_link']

    # 插入图片
    IMG_CFG = CFG['image']
    img_count = 0
    for i, p in enumerate(products):
        row = START_ROW + i
        ws.row_dimensions[row].height = IMG_CFG['row_height']
        # 图片路径: 优先从 skill 目录找，回退到当前目录
        for base in [SKILL_DIR, os.getcwd()]:
            img_path = os.path.join(base, f'product_images_full/img_{i}.jpg')
            if os.path.exists(img_path): break

        if os.path.exists(img_path):
            xl_img = XLImage(img_path)
            mark = AnchorMarker(
                col=14, colOff=pixels_to_EMU(IMG_CFG['col_off_px']),
                row=row - 1, rowOff=pixels_to_EMU(IMG_CFG['row_off_px'])
            )
            xl_img.anchor = OneCellAnchor(
                _from=mark,
                ext=XDRPositiveSize2D(
                    cx=pixels_to_EMU(IMG_CFG['display_size_px']),
                    cy=pixels_to_EMU(IMG_CFG['display_size_px'])
                )
            )
            ws.add_image(xl_img)
            img_count += 1
        else:
            warn(f'图片缺失: {img_path}')
    ok(f'图片嵌入: {img_count}/{len(products)}')

    # 合并单元格
    def merge_column_by_box(ws, col_idx, start_row, products):
        box_groups = {}
        for i, p in enumerate(products):
            r = start_row + i
            bn = p['boxNo']
            box_groups.setdefault(bn, []).append(r)
        for bn, rows in box_groups.items():
            if len(rows) > 1:
                ws.merge_cells(start_row=rows[0], start_column=col_idx, end_row=rows[-1], end_column=col_idx)
            ws.cell(rows[0], col_idx).alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

    merge_column_by_box(ws, 1, START_ROW, products)
    merge_column_by_box(ws, 14, START_ROW, products)
    ok(f'A/N列合并: {len(set(p["boxNo"] for p in products))} 个箱')

    for row in range(START_ROW, START_ROW + len(products)):
        ws.cell(row, 7).alignment = Alignment(wrap_text=True, vertical='center')
        ws.cell(row, 8).alignment = Alignment(wrap_text=True, vertical='center')

    # 保存
    suffix = OUTPUT_SUFFIX or '-发票'
    output_file = f'{shipment_id}{suffix}.xlsx'
    tmp_path = os.path.join(SKILL_DIR, 'output', output_file)
    os.makedirs(os.path.dirname(tmp_path), exist_ok=True)
    wb.save(tmp_path)
    ok(f'已保存: {tmp_path}')
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    target_path = os.path.join(OUTPUT_DIR, output_file)
    shutil.copy2(tmp_path, target_path)
    ok(f'已复制: {target_path}')

    # ========== 关卡5: 逐列对比 ==========
    print('\n' + '=' * 60)
    print('【关卡5】填表后逐列对比')
    print('=' * 60)

    wb_check = load_workbook(tmp_path)
    ws_check = wb_check.active

    COL_CHECKS = [
        (1,  '箱序号',   lambda p: str(p['boxIndex'])),
        (2,  '中文品名', lambda p: p['name_cn']),
        (3,  '英文品名', lambda p: p['name_en']),
        (4,  '带电/带磁', lambda p: '否'),
        (7,  '材质',     lambda p: p['material']),
        (8,  '用途',     lambda p: p['usage']),
        (10, '数量',     lambda p: p['qty']),
        (11, '单价',     lambda p: p['price_jpy']),
        (13, 'FNSKU',    lambda p: p['fnsku']),
        (14, 'FBA箱号',  lambda p: re.sub(r'P\d+$', '', p['boxNo'])),
        (16, '亚马逊链接', lambda p: p['amazon_link']),
    ]

    mr_list = list(ws_check.merged_cells.ranges)
    merged_map = {}
    for mr in mr_list:
        if mr.min_row >= START_ROW:
            for r in range(mr.min_row, mr.max_row + 1):
                merged_map[(r, mr.min_col)] = mr.min_row

    col_mismatches = 0
    for i, p in enumerate(products):
        row = START_ROW + i
        for col_idx, col_name, getter in COL_CHECKS:
            expected = getter(p)
            check_row = merged_map.get((row, col_idx), row)
            actual = ws_check.cell(check_row, col_idx).value
            if isinstance(expected, float) and isinstance(actual, (int, float)):
                if abs(expected - actual) > 0.01:
                    col_mismatches += 1
                    block(f'Row{row} {col_name}({col_idx}): 期望={expected} 实际={actual}')
            elif str(expected) != str(actual):
                col_mismatches += 1
                block(f'Row{row} {col_name}({col_idx}): 期望="{expected}" 实际="{actual}"')

    for i in range(len(products)):
        row = START_ROW + i
        l_val = ws_check.cell(row, 12).value
        if not str(l_val).startswith('='):
            block(f'Row{row} L列不是公式: {l_val}')
            col_mismatches += 1

    if col_mismatches == 0:
        ok(f'逐列对比: {len(products)} × {len(COL_CHECKS) + 1} 列全部匹配')

    # P-K 交叉验证
    print('\n--- P-K 交叉验证 ---')
    pk_mismatches = 0
    for i, p in enumerate(products):
        row = START_ROW + i
        pi = prices.get(p['asin'])
        fetched = pi['amount'] if pi and isinstance(pi, dict) and pi.get('amount') else 'NONE'
        k_val = p['price_jpy']
        status = 'OK'
        if fetched != 'NONE' and k_val == 0:
            status = 'MISMATCH! (有货但K=0)'
            pk_mismatches += 1
        elif fetched == 'NONE' and k_val > 0:
            status = 'MISMATCH! (无货但K>0)'
            pk_mismatches += 1
        print(f'  [{status}] Row{row}: {p["asin"]} | K={k_val} | Amazon={fetched}')
        if status != 'OK': block(status)

    if pk_mismatches == 0:
        ok('P-K 交叉验证: 全部通过')

    # ========== 关卡6: 最终结构 ==========
    print('\n' + '=' * 60)
    print('【关卡6】最终结构校验')
    print('=' * 60)

    excel_row_count = 0
    for row in range(START_ROW, START_ROW + 200):
        if ws_check.cell(row, 10).value is not None:
            excel_row_count += 1
        else:
            break
    if excel_row_count != len(products):
        block(f'Excel行数({excel_row_count}) ≠ 产品数({len(products)})')
    else:
        ok(f'Excel行数 = 产品数 = {len(products)}')

    if img_count != len(products):
        block(f'图片数({img_count}) ≠ 产品数({len(products)})')
    else:
        ok(f'图片数 = 产品数 = {img_count}')

    a_merged = [m for m in mr_list if m.min_col == 1 and m.min_row >= START_ROW]
    n_merged = [m for m in mr_list if m.min_col == 14 and m.min_row >= START_ROW]
    ok(f'A列合并: {len(a_merged)} 区域, N列合并: {len(n_merged)} 区域')

    b2_val = ws_check['B2'].value
    a8_val = ws_check['A8'].value
    if not b2_val: block('B2 AWB 为空')
    else: ok(f'B2 AWB = {b2_val}')
    if not a8_val: block('A8 CONSIGNEE 为空')
    else: ok(f'A8 CONSIGNEE = {a8_val}')

    # ========== 最终结果 ==========
    print('\n' + '=' * 60)
    if errors:
        print(f'⛔ 生成失败! {len(errors)} 个阻断错误:')
        for e in errors: print(f'  {e}')
        sys.exit(1)
    else:
        print(f'✅ 发票生成成功! ({len(warnings)} 个警告)')
        if warnings:
            for w in warnings: print(f'  {w}')
        print(f'  文件: {target_path}')
        print(f'  货件: {shipment_id} | {len(products)} 品 | {total_boxes} 箱 | 仓: {warehouse_code}')

    # 保存翻译缓存
    with open(trans_path, 'w', encoding='utf-8') as f:
        json.dump(TRANSLATION_DICT, f, ensure_ascii=False, indent=2)
    ok(f'翻译缓存已保存 ({len(TRANSLATION_DICT)} 条)')


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('用法: python fill_invoice.py <shipment_data.json> <asin_prices.json>')
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
