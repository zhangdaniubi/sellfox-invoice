# sellfox-invoice 一键部署提示词

复制下面这段话到你的 WorkBuddy 对话中，WorkBuddy 会自动完成安装：

---

```
请帮我从 GitHub 安装 sellfox-invoice Skill：

1. Clone 仓库:
   git clone https://github.com/zhangdaniubi/sellfox-invoice.git ~/.workbuddy/skills/sellfox-invoice/

2. 安装依赖:
   - Node: cd ~/.workbuddy/skills/sellfox-invoice && npm install playwright
   - Python: pip install openpyxl

3. 复制配置文件:
   cp ~/.workbuddy/skills/sellfox-invoice/config.example.json ~/.workbuddy/skills/sellfox-invoice/config.json

4. 问我以下信息并填入 config.json:
   - 发票 Excel 模板的完整路径（如 E:/2/发票/新图/新图大陆新图香港模板.xlsx）
   - 发票输出目录（如 E:/2/ai生成发票/新图/）
   - 文件名后缀（如 -新图大陆-DZ02，不需要则留空）
   - Amazon 价格系数（默认 0.7）
   - Amazon 站点域名（默认 www.amazon.co.jp）

5. 部署完成后告诉我使用方法，然后说"部署成功，你可以试试说'帮我从赛狐提取数据生成发票'"
```

---

## 使用前准备（需要我手动做）

- [ ] Chrome 以调试模式启动：创建快捷方式，目标填 `"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222`
- [ ] 双击快捷方式启动 Chrome，登录 sellfox.com
- [ ] 打开目标货件的「装箱信息」页面，切换到「产品」视图，点击「展开更多商品」
