# CS 168 双语教材

[CS 168: Introduction to the Internet](https://cs168.io/) 课程教材的本地镜像，带有完整的中文翻译。

## 在浏览器中查看

用浏览器打开 `site/index.html`，页面底部有语言切换按钮：

- **中文** — 显示中文翻译
- **English** — 显示英文原文
- **中英对照** — 上下对照显示

## 翻译内容

- 62 个页面，3809 个翻译块，100% 覆盖
- 技术术语采用中文在前、英文括号标注的惯例（如 路由(routing)）
- 侧边栏导航完整翻译

## 项目结构

```
site/                       本地镜像站点（HTML + 静态资源）
  cs168-local/
    localize.js             前端双语切换逻辑
    translations.js         合并后的翻译数据（由 build 生成）
translations/               翻译源文件（每页一个 JSON）
tools/
  mirror_textbook.py        从 textbook.cs168.io 拉取页面生成镜像
  extract_translation_blocks.py   从 HTML 提取待翻译文本块
  build_translations_js.py        将翻译 JSON 合并为 translations.js
```

## 更新翻译

1. 编辑 `translations/` 下对应的 JSON 文件
2. 运行 `python3 tools/build_translations_js.py`
3. 刷新浏览器

## 添加新翻译

1. 确保 `site/` 下有待翻译的 HTML 页面
2. 运行 `python3 tools/extract_translation_blocks.py` 更新骨架
3. 在 `translations/` 下创建对应的 JSON 文件，填写 `zh_html` 字段
4. 运行 `python3 tools/build_translations_js.py`

## License

教材原文版权归 CS 168 课程所有。中文翻译采用相同许可证。
