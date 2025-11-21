# Project Architecture

```shell
knpu
├── crawler
│   ├── main_web.py
│   ├── main.py
│   ├── Package
│   │   ├── __init__.py
│   │   ├── ChinaCrawlerPackage
│   │   │   ├── __init__.py
│   │   │   ├── ChinaDailyCrawlerModule.py
│   │   │   ├── ChinaHuanqiuCrawlerModule.py
│   │   │   └── ChinaSinaCrawlerModule.py
│   │   ├── CrawlerModule.py
│   │   ├── error code list.docx
│   │   ├── GoogleModule.py
│   │   ├── mysql.py
│   │   ├── NaverCrawlerPackage
│   │   │   ├── __init__.py
│   │   │   ├── NaverBlogCrawlerModule.py
│   │   │   ├── NaverCafeCrawlerModule.py
│   │   │   └── NaverNewsCrawlerModule.py
│   │   ├── OtherCrawlerPackage
│   │   │   ├── __init__.py
│   │   │   ├── DcinsideCrawlerModule.py
│   │   │   └── YouTubeCrawlerModule.py
│   │   ├── test.py
│   │   └── ToolModule.py
│   ├── test.py
│   └── update_ip.py
├── manager
│   ├── app
│   │   ├── assets
│   │   │   ├── __init__.py
│   │   │   ├── app_icon.icns
│   │   │   ├── chatgpt_logo.png
│   │   │   ├── download_icon.ico
│   │   │   ├── exe_icon.ico
│   │   │   ├── exe_icon.png
│   │   │   ├── gui.ui
│   │   │   ├── malgun.ttf
│   │   │   ├── microphone.png
│   │   │   ├── search.png
│   │   │   └── setting.png
│   │   ├── compile
│   │   │   ├── build.py
│   │   │   ├── build.spec
│   │   │   ├── setup.iss
│   │   │   └── upload.py
│   │   ├── config.py
│   │   ├── core
│   │   │   ├── boot.py
│   │   │   ├── setting.py
│   │   │   ├── shortcut.py
│   │   │   └── thread.py
│   │   ├── libs
│   │   │   ├── __init__.py
│   │   │   ├── admin.py
│   │   │   ├── amout.py
│   │   │   ├── analysis.py
│   │   │   ├── console.py
│   │   │   ├── kemkim.py
│   │   │   ├── mysql.py
│   │   │   ├── path.py
│   │   │   └── viewer.py
│   │   ├── main.py
│   │   ├── pages
│   │   │   ├── __init__.py
│   │   │   ├── page_analysis.py
│   │   │   ├── page_board.py
│   │   │   ├── page_database.py
│   │   │   ├── page_settings.py
│   │   │   ├── page_user.py
│   │   │   ├── page_web.py
│   │   │   └── page_worker.py
│   │   ├── services
│   │   │   ├── __init__.py
│   │   │   ├── api.py
│   │   │   ├── auth.py
│   │   │   ├── crawldb.py
│   │   │   ├── csv.py
│   │   │   ├── llm.py
│   │   │   ├── logging.py
│   │   │   ├── pushover.py
│   │   │   └── update.py
│   │   ├── ui
│   │   │   ├── __init__.py
│   │   │   ├── dialogs.py
│   │   │   ├── finder.py
│   │   │   ├── status.py
│   │   │   ├── style.py
│   │   │   └── table.py
│   │   └── windows
│   │       ├── __init__.py
│   │       ├── main_window.py
│   │       └── splash_window.py
│   ├── requirements.txt
│   ├── server
│   │   ├── app
│   │   │   ├── db
│   │   │   │   └── __init__.py
│   │   │   ├── format
│   │   │   │   ├── engkor_list.csv
│   │   │   │   ├── exception_list.csv
│   │   │   │   └── tokenize_list.csv
│   │   │   ├── libs
│   │   │   │   ├── exceptions.py
│   │   │   │   ├── jwt.py
│   │   │   │   ├── kemkim.py
│   │   │   │   └── progress.py
│   │   │   ├── main.py
│   │   │   ├── models
│   │   │   │   ├── __init__.py
│   │   │   │   ├── analysis_model.py
│   │   │   │   ├── board_model.py
│   │   │   │   ├── crawl_model.py
│   │   │   │   └── user_model.py
│   │   │   ├── routes
│   │   │   │   ├── __init__.py
│   │   │   │   ├── analysis_routes.py
│   │   │   │   ├── auth_routes.py
│   │   │   │   ├── board_routes.py
│   │   │   │   ├── crawl_routes.py
│   │   │   │   ├── format_routes.py
│   │   │   │   ├── ping_routes.py
│   │   │   │   └── user_routes.py
│   │   │   ├── services
│   │   │   │   ├── __init__.py
│   │   │   │   ├── analysis_service.py
│   │   │   │   ├── auth_service.py
│   │   │   │   ├── board_service.py
│   │   │   │   ├── crawl_service.py
│   │   │   │   └── user_service.py
│   │   │   └── utils
│   │   │       ├── getsize.py
│   │   │       ├── mail.py
│   │   │       ├── mongo.py
│   │   │       ├── pushover.py
│   │   │       └── zip.py
│   │   ├── graph_analysis.py
│   │   └── run.py
│   └── web
│       ├── app
│       │   ├── main.py
│       │   └── static
│       │       └── index.html
│       └── run.py
├── README.md
├── requirements.txt
└── setup.sh
```