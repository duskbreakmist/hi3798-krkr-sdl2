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

## Corrections to common assumptions

- `-gclim` is a graphics-cache limit in MiB, not the TJS garbage-collection threshold.
- An environment variable named `KRKR_FPS` is not proof of a functioning limiter; no read was found in the inspected engine directories.
- 30 divides 60. Actual frame pacing still needs measurement.
- The 47–63 MiB/frame estimate depends on surface dimensions, dirty regions and transfer assumptions; it is not measured traffic.
- SDL2's 2D API can use GPU renderers. The current software renderer and the upstream CPU layer composition are separate choices.

Sources: [SDL2 GLES2 renderer](https://github.com/libsdl-org/SDL/blob/release-2.26.5/src/render/opengles2/SDL_render_gles2.c), [SDL2 backend build options](https://github.com/libsdl-org/SDL/blob/release-2.26.5/CMakeLists.txt), [Mesa Lima](https://docs.mesa3d.org/drivers/lima.html), [EGL DMA-BUF import](https://registry.khronos.org/EGL/extensions/EXT/EGL_EXT_image_dma_buf_import.txt).
