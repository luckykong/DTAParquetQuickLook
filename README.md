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

### v0.1 发布说明

`v0.1` 是第一个公开测试版本。GitHub Release 中提供的预编译应用具有以下限制：

- 仅包含 `arm64` 二进制，只支持 Apple Silicon Mac。
- 使用 ad-hoc 签名，未使用 Apple Developer ID 签名，也未经过 Apple 公证。
- macOS Gatekeeper 可能阻止从网络下载的应用。推荐优先按照下文说明从源码构建。
- 如果你已核对 Release 中的 SHA-256 校验值并信任该文件，可以在安装后执行：

```bash
xattr -dr com.apple.quarantine "/Applications/DTA Parquet Quick Look.app"
```

- 预编译应用不内置 Python、pandas 或 PyArrow，仍需按照下文“安装”第 1 步
  配置本地 Python 环境。

### 系统与依赖

- macOS 12 或更高版本。
- Python 3，以及 `pandas`、`pyarrow`（配置方法见下文“安装”第 1 步）。
- 仅从源码构建时需要 Apple Command Line Tools：`xcode-select --install`。
  不需要安装完整 Xcode。

### 构建

以下两种方式获取应用，任选其一。

**方式一：下载发布版本**

从 [GitHub Releases](https://github.com/luckykong/DTAParquetQuickLook/releases)
下载预编译的 `DTA Parquet Quick Look.app`（限制见上文“v0.1 发布说明”，
包括 Gatekeeper 与 quarantine 的处理）。无需构建，直接进入下文“安装”。

**方式二：从源码构建**

```bash
./build.sh
```

构建产物位于 `build/DTA Parquet Quick Look.app`。

### 安装

#### 第 1 步（必须）：配置 Python 环境

> **重要：应用不内置 Python、pandas 或 PyArrow。** 跳过本步骤直接打开预览，
> 只会看到类似 `DATA PREVIEW ERROR: ModuleNotFoundError: No module named
> 'pyarrow'` 的错误，看不到数据。请务必配置一个自定义 Python 环境，环境中
> 必须预先安装 `pandas` 和 `pyarrow` 两个模块，并把解释器路径写入
> `python-path` 配置文件。

```bash
conda create -n dta-parquet-quicklook python pandas pyarrow
conda activate dta-parquet-quicklook
mkdir -p "$HOME/Library/Application Support/DTA Parquet Quick Look"
which python > "$HOME/Library/Application Support/DTA Parquet Quick Look/python-path"
```

不使用 conda 时，也可以用其它 Python（例如 Homebrew 的 python3）安装
`pandas` 和 `pyarrow`，再把该解释器的绝对路径写入上面的 `python-path`
文件。程序虽然会自动检查常见的 Homebrew、Conda 和系统 Python 路径，但这些
解释器通常没有安装依赖，请不要依赖自动检测。`python-path` 配置文件优先级
最高，文件内容应为 Python 可执行文件的绝对路径。

#### 第 2 步：安装应用并注册扩展

```bash
pluginkit -r "/Applications/DTA Parquet Quick Look.app/Contents/PlugIns/DTA Parquet Preview.appex" 2>/dev/null || true
rm -rf "/Applications/DTA Parquet Quick Look.app"
ditto "build/DTA Parquet Quick Look.app" "/Applications/DTA Parquet Quick Look.app"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister \
  -f "/Applications/DTA Parquet Quick Look.app"
pluginkit -a "/Applications/DTA Parquet Quick Look.app/Contents/PlugIns/DTA Parquet Preview.appex"
qlmanage -r cache
qlmanage -r
```

使用下载的发布版本时，把 `ditto` 命令中的源路径
`build/DTA Parquet Quick Look.app` 替换为解压后应用的实际路径，其余命令不变。

#### 第 3 步：启用扩展

如果 Finder 尚未启用扩展，请在“系统设置 → 通用 → 登录项与扩展 → Quick Look”
中启用 DTA Parquet Preview。重新安装后，关闭并重新打开已有的 Quick Look 窗口。

`qlmanage -r cache` 清除预览缓存，`qlmanage -r` 重启 Quick Look 守护进程。
如果扩展显示为已启用、但按空格仍看不到数据，通常是注册记录陈旧或系统缓存了
旧的失败结果，重新执行上面这组命令即可恢复。

### 卸载

```bash
pluginkit -r "/Applications/DTA Parquet Quick Look.app/Contents/PlugIns/DTA Parquet Preview.appex"
rm -rf "/Applications/DTA Parquet Quick Look.app"
qlmanage -r cache
qlmanage -r
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

### AI 构建声明

本项目的大部分代码、界面样式、构建脚本和文档由人工提出需求并在 AI 辅助下
生成、修改和调试。项目维护者对功能方向作出决定，并在本地完成了 DTA、Parquet、
大文件边界、Quick Look 交互、隐私字符串和签名检查。AI 辅助并不等同于独立的
安全审计；在生产环境或安全敏感场景使用前，请自行审查源码和依赖。

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

### v0.1 release notes

`v0.1` is the first public test release. The prebuilt app attached to the
GitHub Release has the following limitations:

- It contains `arm64` binaries only and supports Apple Silicon Macs only.
- It is ad-hoc signed, not signed with an Apple Developer ID, and not notarized
  by Apple.
- macOS Gatekeeper may block an app downloaded from the internet. Building from
  source using the instructions below is recommended.
- After verifying the SHA-256 checksum published with the Release, trusted
  users may remove the quarantine attribute after installation:

```bash
xattr -dr com.apple.quarantine "/Applications/DTA Parquet Quick Look.app"
```

- The prebuilt app does not bundle Python, pandas, or PyArrow. A local Python
  environment must still be configured as described in Step 1 of Install below.

### Requirements

- macOS 12 or later.
- Python 3 with `pandas` and `pyarrow` (configured in Step 1 of Install below).
- Apple Command Line Tools (`xcode-select --install`) — only needed when
  building from source. Full Xcode is not required.

### Build

Get the app in either of two ways.

**Option 1: download a release**

Download the prebuilt `DTA Parquet Quick Look.app` from
[GitHub Releases](https://github.com/luckykong/DTAParquetQuickLook/releases)
(see the v0.1 release notes above for its limitations, including Gatekeeper
and quarantine handling). No build step is needed; continue with Install below.

**Option 2: build from source**

```bash
./build.sh
```

The built app is placed at `build/DTA Parquet Quick Look.app`.

### Install

#### Step 1 (required): configure the Python environment

> **Important: the app does not bundle Python, pandas, or PyArrow.** If you
> skip this step, pressing Space will only show an error such as
> `DATA PREVIEW ERROR: ModuleNotFoundError: No module named 'pyarrow'`
> instead of your data. You must set up a dedicated Python environment with
> the `pandas` and `pyarrow` modules preinstalled, and write the interpreter
> path to the `python-path` configuration file.

```bash
conda create -n dta-parquet-quicklook python pandas pyarrow
conda activate dta-parquet-quicklook
mkdir -p "$HOME/Library/Application Support/DTA Parquet Quick Look"
which python > "$HOME/Library/Application Support/DTA Parquet Quick Look/python-path"
```

Without conda, any other Python (for example Homebrew's python3) also works
as long as `pandas` and `pyarrow` are installed in it; write that
interpreter's absolute path into the `python-path` file above. The app does
probe common Homebrew, Conda, and system Python locations, but those
interpreters usually lack the required modules — do not rely on
auto-detection. The `python-path` configuration file takes precedence and
must contain the absolute path to the Python executable.

#### Step 2: install the app and register the extension

```bash
pluginkit -r "/Applications/DTA Parquet Quick Look.app/Contents/PlugIns/DTA Parquet Preview.appex" 2>/dev/null || true
rm -rf "/Applications/DTA Parquet Quick Look.app"
ditto "build/DTA Parquet Quick Look.app" "/Applications/DTA Parquet Quick Look.app"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister \
  -f "/Applications/DTA Parquet Quick Look.app"
pluginkit -a "/Applications/DTA Parquet Quick Look.app/Contents/PlugIns/DTA Parquet Preview.appex"
qlmanage -r cache
qlmanage -r
```

When installing a downloaded release, replace the `ditto` source path
`build/DTA Parquet Quick Look.app` with the path of the unpacked app; the
other commands stay the same.

#### Step 3: enable the extension

If Finder has not enabled the extension, enable DTA Parquet Preview in
System Settings → General → Login Items & Extensions → Quick Look. Close and
reopen any existing Quick Look window after reinstalling.

`qlmanage -r cache` clears the preview cache and `qlmanage -r` restarts the
Quick Look daemon. If the extension shows as enabled but pressing Space still
shows no data, the registration record is usually stale or a previous failure
is cached; rerunning the commands above restores it.

### Uninstall

```bash
pluginkit -r "/Applications/DTA Parquet Quick Look.app/Contents/PlugIns/DTA Parquet Preview.appex"
rm -rf "/Applications/DTA Parquet Quick Look.app"
qlmanage -r cache
qlmanage -r
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

### AI development disclosure

Most of the code, interface styling, build scripts, and documentation in this
project were generated, revised, and debugged with AI assistance from
human-provided requirements. The project maintainer made the product decisions
and performed local checks covering DTA and Parquet files, large-file bounds,
Quick Look interactions, privacy strings, and code signatures. AI assistance
is not an independent security audit. Review the source and dependencies before
using the project in production or security-sensitive environments.

## License

MIT. See [LICENSE](LICENSE).
