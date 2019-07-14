# OTA-maker

本工具可以根据输入自动生成OTA增量升级包<br>
This tool can automatically generate OTA incremental upgrade package.

## Requirements
- x86_64 enviroment (Windows Or Linux)
- Python 3
- 安装 Python 3 的 bsdiff4 库<br>
  (You need to install a extension library called **bsdiff4** with **pip** before using this script.)<br>
  `pip3 install bsdiff4`

## Usage
`makeota.py <OLD_ZIP> <NEW_ZIP> [OUT_PATH]`

## License
- MIT

## Note
- 支持对 Android KitKat+ ROM 的打包(并未对KitKat以下的版本做测试)，特殊格式打包的ROM除外<br>
  (Supported KitKat+ ROM(Did not test the previous version of KitKat). Not supported Rom which packaged with special methods.)
- ~~不允许跨 Android 版本的OTA~~ (不做限制，但不保证可用性)<br>
  ~~Not allowed cross Android version OTA~~ (no limit, but does not guarantee the availability)
- 部分代码来自(Part of the code comes from) [Generic_OTA_Package_Generation_Script](https://github.com/Pzqqt/Generic_OTA_Package_Generation_Script)
- 一些不属于我自己的文件或其源码的来源:<br>
  (Sources for some non-owned binary files & source code used:)
    - **sdat2img.py**: https://github.com/xpirt/sdat2img
    - **bootimg.py**: https://github.com/jpacg/bootimg
    - **bin/sefcontext_decompile**: https://github.com/wuxianlin/sefcontext_decompile
    - **bin/brotli**: https://github.com/google/brotli
    - **bin/imgextractor.exe**: https://4pda.ru/forum/index.php?showtopic=496786
    - **bin/update-binary, bin/update-binary_64**: https://github.com/LineageOS/android_bootable_recovery/tree/lineage-15.1/updater
