# paiping-app-spider

[少数派](https://sspai.com) 网站文章爬虫，专注于抓取「派评」栏目中的应用推荐文章并切分。

## 功能

- 自动抓取少数派「派评 - 近期值得关注的 App」类文章
- 解析文章内容，按应用拆分提取
- 将每个应用保存为独立的 Markdown 文件
- 自动下载并本地化文章中的图片

## 依赖

```
requests
beautifulsoup4
markdownify
pytest
pyrallis
```

安装依赖：
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 使用

```bash
source venv/bin/activate
python main.py \
--update [bool]  \ # 同步新发布的文章，若本地无文章则须使用 months 参数抓取
--months [months] \ # 抓取近几个月内的文章，若本地有时间范围内的文章，会被覆盖
--page_size [page_size] \ # 每次分页查询大小
--output_dir [output_dir] \ # 结果保存目录，默认 data/
```

抓取结果默认保存在 `data/` 目录下，格式为：
```
data/YYYY-MM-DD/App标题-[支持平台列表].md
data/YYYY-MM-DD/images/图片.jpg
```

## 项目结构

```
paiping-app-spider/
├── main.py           # 入口脚本
├── spider/
│   ├── data.py       # 数据类型定义
│   ├── fetcher.py    # API请求模块
│   ├── parser.py     # 解析模块
│   ├── saver.py      # 文件保存模块
│   └── util.py       # 工具函数
├── requirements.txt
├── data/             # 输出目录
├── scripts/          # 执行脚本
└── spider.log        # 日志
```
