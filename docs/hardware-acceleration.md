# Hardware acceleration investigation

Updated 2026-10-27. This is a feasibility result, not an accelerated game build or an FPS improvement claim.

## Newly verified: an armhf TDE path

The HiSilicon SDK contains small TDE userspace and MMZ allocation modules. Compiling those modules locally for Debian armhf produced an ARM hard-float executable whose only dynamic dependency was libc. It did not link the existing softfp vendor libraries.

An offscreen test on the target board passed:

- Three 64×64 ARGB8888 surfaces, totaling 48 KiB of MMZ memory.
- Hardware fill and copy, checking all pixels.
- One constant-color alpha blend, checking the first pixel's RGB result.
- Unmap and allocation deletion both returned success.
- Xorg remained running; framebuffer geometry and depth were unchanged.

The blend produced `0xbf80007f`: RGB approximately half red and half blue, alpha 191. This is an observation for that specific configuration, not proof of equivalence with every KiriKiri blend or alpha-preservation mode.

The SDK sources, SDK headers, vendor-derived objects, executable and raw machine logs are not distributed in this repository.

## Recommended first integration

Keep the existing armhf engine and SDL/X11 presentation. Add an optional TDE path at bitmap `Blt` / `CopyRect`, using persistent MMZ surfaces and a CPU fallback for unmatched operations.

This does not require changing Xorg: the completed image can still go through the existing SDL texture upload and window presentation. Directly drawing into a framebuffer owned by Xorg is a different design and has shadow-buffer ownership problems.

Requirements before enabling it in a game:

1. Compare actual engine copy/fill/alpha functions against TDE, including destination alpha, premultiplication, opacity, clipping, overlap and stride.
2. Verify cached MMZ ownership and CPU/device cache synchronization. Re-uploading every source through uncached memory could erase the benefit.
3. Batch sufficiently large operations; do not replace every short scanline or glyph with a synchronous IOCTL.
4. Keep the CPU and device views coherent when switching to unsupported blend/blur/mask operations.
5. Measure complete 720p/1080p upload, job, wait, synchronization and read costs against NEON.
6. Measure fixed-scene FPS, frame-time percentiles and click-to-visible-change latency. Hardware throughput alone is not game FPS.

TDE does not automatically cover arbitrary blur, affine transforms, special blend modes or Motion rendering.

## Other routes

| Route | Assessment |
| --- | --- |
| DirectFB/TDE or custom fullscreen presentation | Possible follow-up. Rebuilding a limited C graphics stack is another option; moving the entire C++ engine to softfp is not inherently required. Presentation acceleration alone leaves CPU layer composition intact. |
| Mali GLES2 composition | Real softfp Mali rendering already worked elsewhere in the board project. The engine needs a compatible backend, or a separate softfp rendering service with batched commands and shared resources. A final-frame upload alone will not eliminate CPU alpha/blur work. |
| Lima/DRM/KMS | Longer-term graphics-stack work, not an install-only fix for the current vendor kernel. GPU rendering and display/scanout are separate responsibilities. |

Avoid assuming that private Mali DMA-BUF import requires a DRM display node. Conversely, successful NV21 texture import does not prove that shared RGBA FBO output or export back to Xorg works. The existing slow full-frame GPU readback implementation is unsuitable without a different measured transfer path.

A [community newer-kernel port](https://github.com/loonpn/ec6108v9c-linux-kernel/releases/tag/v6.14.3) exists for the same chip family. Its release author lists L1/L2 cache, HDMI/GPU and audio-output problems. These are upstream statements, not tests of that image on this board. It is therefore a research starting point, not a ready-made accelerated desktop replacement; no claim that such ports do not exist is intended.

## DirectFB/Mali follow-up tests

A real, isolated, minimally built DirectFB 1.6.1 core resolved the SDK hard-float DirectFB Mali library's dependencies. The core was built from the original release without the vendor's DirectFB patches; this is not a test of the full vendor framebuffer/TDE stack.

The SDK sample requires an actual `IDirectFBDisplayLayer` as the native EGL display. Passing the default null display crashed and is not counted as a valid compatibility result. The corrected test created a real display-layer object through a dummy-only DirectFB backend, without an on-screen window.

| Case | Result |
| --- | --- |
| SDK320 hard-float DirectFB + dummy layer | Library loaded; DirectFB core/layer and EGL initialization succeeded; 22 configs enumerated; context creation failed with EGL_BAD_CONFIG for all 16 valid GLES2 configs. Releasing the DirectFB objects subsequently crashed. |
| SDK320 hard-float fbdev | 22 configs; all 16 valid GLES2 configs failed context creation with EGL_BAD_CONFIG. |
| SDK310 softfp fbdev, same probe source | GLES2 context and shader draw succeeded. A nonzero floating-point clear API test passed, and all 4,096 rendered pixels matched within the documented 8-bit tolerance. |

The test covered multiple color formats and checked context creation for an additional GLES2 configuration without pbuffer support. It did not silently treat all 22 enumerated configurations as GLES2-renderable.

No desktop services were stopped. The dummy case did not open the framebuffer; the fbdev libraries did open it for queries. No framebuffer mode-write operation was recorded, and geometry/depth/stride were unchanged. No native window presentation, desktop acceleration or game FPS improvement was validated.

This confirms the current kernel/hardware can execute the known softfp GLES2 path. It also shows that installing missing DirectFB dependencies alone does not make these particular hard-float binaries ready for desktop use. The context failure and DirectFB cleanup crash remain unresolved, and the dummy result is not a blanket rejection of a properly matched vendor-patched native stack.

The original probe source is included as `tools/mali-context-probe.c`; vendor libraries, SDK sources, generated binaries and machine logs remain private.

```bash
# Build for the same ARM ABI as the selected library.
$CC -std=gnu99 -O2 tools/mali-context-probe.c -ldl -o work/mali-context-probe
work/mali-context-probe /path/to/private/fbdev/libMali.so
```

The optional `PROBE_WITH_DIRECTFB` build needs matching DirectFB 1.6 headers. Its `--dfb-dummy` argument requires a private module directory containing the dummy system and default window manager only, without framebuffer/devmem backends. Native hardware-backed DirectFB surfaces were not tested.

## Corrections to common assumptions

- `-gclim` is a graphics-cache limit in MiB, not the TJS garbage-collection threshold.
- An environment variable named `KRKR_FPS` is not proof of a functioning limiter; no read was found in the inspected engine directories.
- 30 divides 60. Actual frame pacing still needs measurement.
- The 47–63 MiB/frame estimate depends on surface dimensions, dirty regions and transfer assumptions; it is not measured traffic.
- SDL2's 2D API can use GPU renderers. The current software renderer and the upstream CPU layer composition are separate choices.

Sources: [SDL2 GLES2 renderer](https://github.com/libsdl-org/SDL/blob/release-2.26.5/src/render/opengles2/SDL_render_gles2.c), [SDL2 backend build options](https://github.com/libsdl-org/SDL/blob/release-2.26.5/CMakeLists.txt), [Mesa Lima](https://docs.mesa3d.org/drivers/lima.html), [EGL DMA-BUF import](https://registry.khronos.org/EGL/extensions/EXT/EGL_EXT_image_dma_buf_import.txt).
