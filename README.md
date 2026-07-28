# DTA Parquet Quick Look

[中文](#中文) | [English](#english)

## 中文

一个轻量的 macOS Quick Look 扩展。在 Finder 中选中 Stata `.dta` 或
Apache Parquet `.parquet` 文件并按空格，即可用对齐的表格快速查看数据结构。

### 功能

- 显示全部变量，不限制列数。
- 显示变量名、数据类型、文件大小、总行数和变量数。
- 支持中文、英文、数字、空字符串和缺失值。
- 表头和行号固定，支持横向及纵向滚动。
- 不超过 2,000 行且不超过 100,000 个单元格时，提供
  `First 50 / All N` 切换。
- 更大的数据集只读取前 500 行，提供 `First 50 / First 500` 切换，
  不会读取完整数据文件。
- 使用纯 HTML/CSS 表格，不执行页面 JavaScript。

### 系统与依赖

- macOS 12 或更高版本。
- Apple Command Line Tools：`xcode-select --install`。不需要安装完整 Xcode。
- Python 3，以及 `pandas`、`pyarrow`。

推荐使用独立环境：

```bash
conda create -n dta-parquet-quicklook python pandas pyarrow
conda activate dta-parquet-quicklook
mkdir -p "$HOME/Library/Application Support/DTA Parquet Quick Look"
which python > "$HOME/Library/Application Support/DTA Parquet Quick Look/python-path"
```

程序也会自动检查常见的 Homebrew、Conda 和系统 Python 路径。配置文件优先级
更高，文件内容应为 Python 可执行文件的绝对路径。

### 构建与安装

```bash
./build.sh
pluginkit -r "/Applications/DTA Parquet Quick Look.app/Contents/PlugIns/DTA Parquet Preview.appex" 2>/dev/null || true
rm -rf "/Applications/DTA Parquet Quick Look.app"
ditto "build/DTA Parquet Quick Look.app" "/Applications/DTA Parquet Quick Look.app"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister \
  -f "/Applications/DTA Parquet Quick Look.app"
pluginkit -a "/Applications/DTA Parquet Quick Look.app/Contents/PlugIns/DTA Parquet Preview.appex"
qlmanage -r cache
```

如果 Finder 尚未启用扩展，请在“系统设置 → 通用 → 登录项与扩展 → Quick Look”
中启用 DTA Parquet Preview。重新安装后，关闭并重新打开已有的 Quick Look 窗口。

### 卸载

```bash
pluginkit -r "/Applications/DTA Parquet Quick Look.app/Contents/PlugIns/DTA Parquet Preview.appex"
rm -rf "/Applications/DTA Parquet Quick Look.app"
qlmanage -r cache
```

### 隐私与安全

- 没有遥测、分析、账户系统或网络请求。
- 文件只在本机读取；预览数据不会保存到项目目录，也不会上传。
- Quick Look 提供程序运行在沙盒中，通过内嵌的本地 XPC 服务调用固定的
  Python 脚本；文件路径作为进程参数传递，不经过 shell。
- 所有表头和单元格内容在写入 HTML 前都会转义。
- 渲染任务有 15 秒超时，并限制为完整的小型数据集或大型数据集的前 500 行。

这不是经过第三方审计的安全产品。解析工作依赖 pandas 和 PyArrow；请及时更新
依赖。恶意构造的文件或包含极多变量的文件仍可能导致依赖解析错误或较高的内存
占用。不要用不受信任的管理员权限运行本项目。

## English

A lightweight macOS Quick Look extension for Stata `.dta` and Apache Parquet
`.parquet` files. Select a file in Finder and press Space to inspect its
structure in an aligned table.

### Features

- Shows every variable without a column-count limit.
- Shows variable names, data types, file size, row count, and variable count.
- Handles Chinese and English text, numbers, empty strings, and missing values.
- Keeps headers and row numbers visible while scrolling.
- For datasets with at most 2,000 rows and 100,000 cells, offers a
  `First 50 / All N` switch.
- For larger datasets, reads at most the first 500 rows and offers a
  `First 50 / First 500` switch instead of loading the complete file.
- Uses a real HTML/CSS table and does not execute page JavaScript.

### Requirements

- macOS 12 or later.
- Apple Command Line Tools: `xcode-select --install`. Full Xcode is not required.
- Python 3 with `pandas` and `pyarrow`.

A dedicated environment is recommended:

```bash
conda create -n dta-parquet-quicklook python pandas pyarrow
conda activate dta-parquet-quicklook
mkdir -p "$HOME/Library/Application Support/DTA Parquet Quick Look"
which python > "$HOME/Library/Application Support/DTA Parquet Quick Look/python-path"
```

The app also checks common Homebrew, Conda, and system Python locations. The
configuration file takes precedence and must contain the absolute path to the
Python executable.

### Build and install

```bash
./build.sh
pluginkit -r "/Applications/DTA Parquet Quick Look.app/Contents/PlugIns/DTA Parquet Preview.appex" 2>/dev/null || true
rm -rf "/Applications/DTA Parquet Quick Look.app"
ditto "build/DTA Parquet Quick Look.app" "/Applications/DTA Parquet Quick Look.app"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister \
  -f "/Applications/DTA Parquet Quick Look.app"
pluginkit -a "/Applications/DTA Parquet Quick Look.app/Contents/PlugIns/DTA Parquet Preview.appex"
qlmanage -r cache
```

If Finder has not enabled the extension, enable DTA Parquet Preview in
System Settings → General → Login Items & Extensions → Quick Look. Close and
reopen any existing Quick Look window after reinstalling.

### Uninstall

```bash
pluginkit -r "/Applications/DTA Parquet Quick Look.app/Contents/PlugIns/DTA Parquet Preview.appex"
rm -rf "/Applications/DTA Parquet Quick Look.app"
qlmanage -r cache
```

### Privacy and security

- No telemetry, analytics, accounts, or network requests.
- Files are read locally. Preview data is neither stored in the repository nor
  uploaded.
- The Quick Look provider is sandboxed. Its embedded local XPC service invokes
  a fixed Python script, and passes the file path as a process argument without
  using a shell.
- Headers and cell values are HTML-escaped before rendering.
- Rendering has a 15-second timeout and is bounded to a complete small dataset
  or the first 500 rows of a larger dataset.

This project has not received an independent security audit. Parsing relies on
pandas and PyArrow; keep them updated. A maliciously crafted file or a dataset
with an extreme number of variables may still trigger parser errors or high
memory usage. Do not run the project with administrator privileges on
untrusted files.

## License

MIT. See [LICENSE](LICENSE).
