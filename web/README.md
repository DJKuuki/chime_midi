# web：网页版指南

[`index.html`](index.html) 是《[发车铃分析与创作指南](../docs/发车铃分析与创作指南.md)》的网页版，包含：
- 路线图式的目录
- 两张可以悬停查看数值的图表
- 5 首实践作品的在线试听，播放时卷帘上正在响的音会亮起来

## 怎么打开

把整个仓库克隆或下载下来，用浏览器直接打开 `web/index.html`。

- 页面从 `../compositions/previews/` 读取试听音频，所以要保持仓库原来的目录结构。
- 字体来自 Google Fonts，离线时会退回系统字体，内容不受影响。
- 如果在仓库设置里开启 GitHub Pages，并从 `main` 分支的根目录发布，也可以在 `<Pages 地址>/web/` 直接访问。

## 重新生成

分析数据或实践作品改动之后，运行：

```bash
python web/build.py
```

需要 `numpy`、`librosa`、`pretty_midi`。

- [`template.html`](template.html) 是页面模板。
- [`build.py`](build.py) 从 `analysis/features.csv` 取图表数据，从 `compositions/compose.py` 重建每首作品的卷帘音符，再填进模板生成 `index.html`。
