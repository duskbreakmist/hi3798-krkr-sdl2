# Hi3798 KRKR SDL2 移植实验

面向 Hi3798MV100 / Cortex-A7、Debian 12 armhf 的 KiriKiri SDL2 构建补丁与回归测试。基于 [DrFlyingPig/krkr-ns](https://github.com/DrFlyingPig/krkr-ns) 的固定版本，移植真实的 Motion、PSB 和其他可移植内置插件。

本仓库仅包含源码补丁、工具及经过整理的技术结论；不含商业游戏、汉化资源、字体文件、二进制包、实机快照或存档。当前不发布 Release。

## 已验证与边界

- ARMv7 / NEON / VFPv4 / hard-float，GCC12，独立运行目录。
- SDL2 软件渲染，FreeType 字体，Opus / Vorbis 音频。
- 修复字节缓冲区被强转为 `uint32_t*` 导致的 ARM 非对齐 SIGBUS；675,840 组函数回归通过。
- 在本地合法游戏副本上验证了标题、设置、中文本篇显示及点击推进。
- 当前仍有明显卡顿、内存压力和退出清理超时；长时游玩、影片播放和游戏内存读档尚未完成验收。
- 未接入 Mali GPU 或海思 VDEC。不能把 NEON 或 SDL renderer 名称当成 GPU 加速证据。

## 构建

上游固定提交为 `949faf9a874f54b149a3fe5382cfccb38afb99bb`。

```bash
# 在 Linux 或 WSL 中。构建不修改系统图形库。
export KRKR_WORK="$PWD/work"
bash scripts/fetch-source.sh

# 提供 Debian 12 armhf 的交叉 sysroot，以及匹配的 GCC12 CC/CXX。
export KRKR_SYSROOT=/path/to/armhf-sysroot
export CC=/path/to/arm-linux-gnueabihf-gcc-12
export CXX=/path/to/arm-linux-gnueabihf-g++-12
bash scripts/build.sh
python3 scripts/package.py
```

Linux 主机需有 CMake、make、Python3、curl、pkg-config、ARM binutils。sysroot 需包含 Debian 12 armhf 开发包：`libc6-dev libstdc++-12-dev libsdl2-dev libfreetype-dev libvorbis-dev libwebp-dev libopusfile-dev libjpeg-dev libpng-dev zlib1g-dev libgles2-mesa-dev libegl1-mesa-dev libminizip-dev` 及其依赖。GCC12 的 C++ 头文件与链接搜索目录必须与该 sysroot 匹配；已配置这些选项的编译器包装脚本也可作为 CC/CXX。依赖下载和系统安装由使用者管理。

构建产物为 `$KRKR_WORK/build/krkrsdl2`，打包结果为 `$KRKR_WORK/runtime/`。字体及兼容脚本从固定的上游源码复制，保留对应许可证；请自行检查依赖再分发。

## 板上启动

先登录图形桌面，再在该用户的终端运行，不使用 root：

```bash
python3 scripts/play.py /path/to/legal-game \
  --runtime /path/to/runtime
```

游戏路径需包含 `data.xp3`。启动器默认临时停止 LXQt 壳、退出后恢复；不会注销 X11 会话。日志和配置保存在运行目录旁的 `sessions/`，存档保存在用户数据目录。详情与参数见 `python3 scripts/play.py --help`。其他桌面可使用 `--keep-shell`。

## 文档

- [非对齐故障定位和修复](docs/alignment.md)
- [性能调查与可验证的优化方向](docs/performance.md)
- [公开内容及隐私策略](docs/publication.md)

本项目为实验性移植，不提供游戏资源，也不保证所有游戏兼容。许可证及上游归属见 [LICENSE](LICENSE) 与 [NOTICE.md](NOTICE.md)。
