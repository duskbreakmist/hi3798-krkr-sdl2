#!/usr/bin/env bash
set -euo pipefail
repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
work=${KRKR_WORK:-"$repo/work"}
: "${KRKR_SYSROOT:?Set KRKR_SYSROOT to a Debian12 armhf sysroot}"
: "${CC:?Set CC to your GCC12 ARM cross compiler}"
: "${CXX:?Set CXX to your GCC12 ARM cross compiler}"
mkdir -p "$work"
python3 "$repo/scripts/patch-source.py" "$work/source/krkrsdl2" --diff "$work/source-changes.patch"
cat > "$work/toolchain.cmake" <<EOF
set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR armv7l)
set(CMAKE_C_COMPILER "$CC")
set(CMAKE_CXX_COMPILER "$CXX")
set(CMAKE_AR arm-linux-gnueabihf-ar)
set(CMAKE_RANLIB arm-linux-gnueabihf-ranlib)
set(CMAKE_SYSROOT "$KRKR_SYSROOT")
set(CMAKE_FIND_ROOT_PATH "$KRKR_SYSROOT")
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)
set(CMAKE_C_FLAGS_INIT "-march=armv7-a -mfpu=neon-vfpv4 -mfloat-abi=hard -D_FILE_OFFSET_BITS=64")
set(CMAKE_CXX_FLAGS_INIT "-march=armv7-a -mfpu=neon-vfpv4 -mfloat-abi=hard -D_FILE_OFFSET_BITS=64")
EOF
export PKG_CONFIG_SYSROOT_DIR="$KRKR_SYSROOT"
export PKG_CONFIG_LIBDIR="$KRKR_SYSROOT/usr/lib/arm-linux-gnueabihf/pkgconfig:$KRKR_SYSROOT/usr/share/pkgconfig"
cmake -S "$work/source/krkrsdl2" -B "$work/build" \
  -DCMAKE_TOOLCHAIN_FILE="$work/toolchain.cmake" -DCMAKE_BUILD_TYPE=RelWithDebInfo \
  -DOPTION_ENABLE_EXTERNAL_PLUGINS=OFF -DOPTION_ENABLE_CANVAS=OFF \
  -DKRKRSDL2_ENABLE_PRECOMPILED_HEADERS=OFF -DOPTION_ENABLE_ASYNC_IMAGE_LOAD=ON
cmake --build "$work/build" -j "${KRKR_JOBS:-4}"
