#!/bin/zsh
set -euo pipefail

project_dir=${0:A:h}
build_dir="$project_dir/build"
app_dir="$build_dir/DTA Parquet Quick Look.app"
extension_dir="$app_dir/Contents/PlugIns/DTA Parquet Preview.appex"
xpc_dir="$extension_dir/Contents/XPCServices/DTA Parquet Render.xpc"
module_cache="$build_dir/ModuleCache"

rm -rf "$build_dir"
mkdir -p "$app_dir/Contents/MacOS" "$app_dir/Contents/PlugIns"
mkdir -p "$extension_dir/Contents/MacOS" "$extension_dir/Contents/Resources"
mkdir -p "$xpc_dir/Contents/MacOS" "$xpc_dir/Contents/Resources"
mkdir -p "$module_cache"

cp "$project_dir/Host/Info.plist" "$app_dir/Contents/Info.plist"
cp "$project_dir/Extension/Info.plist" "$extension_dir/Contents/Info.plist"
cp "$project_dir/RenderService/Info.plist" "$xpc_dir/Contents/Info.plist"
cp "$project_dir/Resources/data_preview.py" \
  "$xpc_dir/Contents/Resources/data_preview.py"

/usr/bin/clang \
  "$project_dir/Host/main.m" \
  -o "$app_dir/Contents/MacOS/DTAParquetQuickLook" \
  -fobjc-arc \
  -fblocks \
  -fmodules-cache-path="$module_cache" \
  -mmacosx-version-min=12.0 \
  -framework Cocoa

/usr/bin/clang \
  "$project_dir/Extension/PreviewProvider.m" \
  -o "$extension_dir/Contents/MacOS/DTAParquetPreview" \
  -fobjc-arc \
  -fblocks \
  -fapplication-extension \
  -fmodules-cache-path="$module_cache" \
  -mmacosx-version-min=12.0 \
  -framework Foundation \
  -framework QuickLookUI \
  -framework UniformTypeIdentifiers \
  -Wl,-e,_NSExtensionMain

/usr/bin/clang \
  "$project_dir/RenderService/main.m" \
  -o "$xpc_dir/Contents/MacOS/DTAParquetRender" \
  -fobjc-arc \
  -fblocks \
  -fmodules-cache-path="$module_cache" \
  -mmacosx-version-min=12.0 \
  -framework Foundation \
  -framework Security

/usr/bin/codesign --force --sign - "$xpc_dir"
/usr/bin/codesign --force --sign - \
  --entitlements "$project_dir/Extension/Preview.entitlements" \
  "$extension_dir"
/usr/bin/codesign --force --sign - "$app_dir"

/usr/bin/codesign --verify --deep --strict --verbose=2 "$app_dir"
echo "$app_dir"
