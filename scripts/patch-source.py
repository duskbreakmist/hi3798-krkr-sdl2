#!/usr/bin/env python3
"""Portable built-ins for the pinned krkr-ns tree; do not define __SWITCH__."""
from pathlib import Path
import argparse, difflib, shutil

parser=argparse.ArgumentParser()
parser.add_argument('source', type=Path, help='Pinned upstream krkrsdl2 directory')
parser.add_argument('--diff', type=Path, required=True)
args=parser.parse_args()
root=args.source.resolve()
changes=[]
def edit(name, fn):
    path=root/name
    backup=path.with_name(path.name+'.hi3798-upstream')
    if not backup.exists(): backup.write_bytes(path.read_bytes())
    old=backup.read_text(errors='surrogateescape')
    new=fn(old)
    if path.read_text(errors='surrogateescape')!=new:
        path.write_text(new,errors='surrogateescape')
    changes.extend(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/'+name,tofile='b/'+name))

def cmake(s):
    # Retain only platform-independent built-ins from the Switch source list.
    block=s[s.index('# KRKR-ns built-ins:'):s.index('# KRKR-ns patch: pkg_check_modules')]
    block=block.replace('src/core/sound/sdl2/FFWaveDecoder.cpp','')
    block=block.replace('TVP_FFMPEG_DECODER_IMPLEMENT','')
    block+='\nlist(APPEND KRKRSDL2COMMON_SRC src/core/base/sdl2/Hi3798PortableBootstrap.cpp)\nlist(APPEND KRKRSDL2_LIBS webp vorbisfile vorbis ogg)\nlist(APPEND KRKRSDL2_DEFINITIONS KRKRSDL2_PORTABLE_BUILTINS)\nset_source_files_properties(src/core/sdl2/SDLApplication.cpp PROPERTIES COMPILE_DEFINITIONS KRKRSDL2_RENDERER_FULL_UPDATES)\n'
    s=s.replace('set(KRKRSDL2_CXX_STANDARD 14)','set(KRKRSDL2_CXX_STANDARD 17)')
    # Existing Debian SDL2 is shared and ABI-compatible with the target.
    a=s.index('set(SDL_SHARED_ENABLED_BY_DEFAULT OFF)',s.index('elseif((APPLE AND NOT IOS)'))
    b=s.index('elseif(ANDROID)',a)
    s=s[:a]+'find_package(SDL2 REQUIRED)\nlist(APPEND KRKRSDL2_LIBS ${SDL2_LIBRARIES})\nlist(APPEND KRKRSDL2COMMON_INCLUDES ${SDL2_INCLUDE_DIRS})\n'+block+'\n'+s[b:]
    return s
edit('CMakeLists.txt',cmake)
edit('src/core/base/sdl2/PluginImpl.cpp',lambda s:s.replace('#if defined(__SWITCH__)','#if defined(__SWITCH__) || defined(KRKRSDL2_PORTABLE_BUILTINS)').replace('#ifdef __SWITCH__','#if defined(__SWITCH__) || defined(KRKRSDL2_PORTABLE_BUILTINS)'))
# Portable plugins already fall back to scalar CPU routines off Switch.
# Mirror useful diagnostics to stderr on the isolated Linux probe.
edit('src/core/sdl2/KrkrNSLog.h',lambda s:s.replace('#define KRKRNS_LOG(...)\n','static inline void krkrsdl2_heartbeat_main_progress() {}\n#define KRKRNS_LOG(...)\n'))
def storage(s):
    a=s.index('static std::string krkrns_utf8_of_path')
    b=s.index('extern bool krkrsdl2_is_builtin_plugin_name',a)
    helper=s[a:b]
    return s.replace('#include "tjsCommHead.h"','#include "tjsCommHead.h"\n#include "ScriptMgnIntf.h"\n#ifndef __SWITCH__\n'+helper+'\n#endif\n')
edit('external/krkrz/base/StorageIntf.cpp',storage)
edit('src/core/base/sdl2/StorageImpl.cpp',lambda s:s.replace('ttstr TVPGetAppPath()\n{','ttstr TVPGetAppPath()\n{\n\tif(const char* project=getenv("KRKR_PROJECT"))\n\t\treturn TVPExtractStoragePath(TVPNormalizeStorageName(ttstr(project)));\n',1))
edit('external/krkrz/utils/DebugIntf.cpp',lambda s:s.replace('void TVPAddLog(const ttstr &line, bool appendtoimportant)\n{','void TVPAddLog(const ttstr &line, bool appendtoimportant)\n{\n\tstd::string utf8;\n\tif(TVPUtf16ToUtf8(utf8, line.AsStdString())) { fprintf(stderr, "TJS_LOG: %s\\n", utf8.c_str()); }\n'))
edit('src/core/environ/sdl2/Application.cpp',lambda s:s.replace('void tTVPApplication::ShowException( const tjs_char* e ) {','void tTVPApplication::ShowException( const tjs_char* e ) {\n\tif(getenv("KRKR_BRIEF_ERRORS")) { TVPAddLog(ttstr(TJS_W("HI3798_FATAL_ERROR: ")) + e); return; }'))
edit('src/core/base/sdl2/SystemImpl.cpp',lambda s:s.replace('const bool text_converted = TVPUtf16ToUtf8(t_utf8, t_utf16);','if(getenv("KRKR_LOG_INFORMS")) {\n\t\tTVPAddLog(ttstr(TJS_W("HI3798_INFORMATION: ")) + text);\n\t\tTVPAddLog(ttstr(TJS_W("HI3798_INFORMATION_TRACE: ")) + TJSGetStackTraceString(12));\n\t\treturn; // Only the informational, single-OK path; confirmations remain interactive.\n\t}\n\tconst bool text_converted = TVPUtf16ToUtf8(t_utf8, t_utf16);',1))
edit('external/krkrz/utils/ThreadIntf.cpp',lambda s:'#include <SDL.h>\n'+s)
edit('src/plugins/psbfile/PsbFilePlugin.cpp',lambda s:'#include <SDL.h>\n'+s)
edit('src/core/sdl2/GLComposite.cpp',lambda s:s.replace('void krkrsdl2_glc_bump_version(const void*) {}','// Non-Switch inline implementation is supplied by GLCompositeBridge.h.'))
edit('external/krkrz/visual/LayerBitmapIntf.cpp',lambda s:s.replace('// KRKR-ns Phase 3: engine-side raster accessor for the GL composite module.','#ifdef __SWITCH__\n// KRKR-ns Phase 3: engine-side raster accessor for the GL composite module.')+'\n#endif // Switch GL composite raster accessor\n')
def window_interface(s):
    s=s.replace('#ifdef __SWITCH__\n    // Preserve the compatibility menu entry','#if defined(__SWITCH__) || defined(KRKRSDL2_PORTABLE_BUILTINS)\n    // Preserve the compatibility menu entry',1)
    for name,label in [('OnMouseDown','mouse'),('OnKeyDown','key')]:
        a=s.index('void tTJSNI_BaseWindow::'+name+'(')
        b=s.index('//---------------------------------------------------------------------------',a)
        section=s[a:b]
        section=section.replace('if(!CanDeliverEvents()) return;','if(getenv("KRKR_INPUT_TRACE")) TVPAddLog(ttstr(TJS_W("HI3798_TJS_INPUT='+label+',allowed=")) + ttstr((tjs_int)CanDeliverEvents()));\n\tif(!CanDeliverEvents()) return;',1)
        end=section.rfind('}')
        section=section[:end]+'\tif(getenv("KRKR_INPUT_TRACE")) TVPAddLog(TJS_W("HI3798_TJS_INPUT_RETURNED='+label+'"));\n'+section[end:]
        s=s[:a]+section+s[b:]
    return s
edit('external/krkrz/visual/WindowIntf.cpp',window_interface)
def sdl_application(s):
    s=s.replace('#include "tjsCommHead.h"','#include "tjsCommHead.h"\n#ifndef __SWITCH__\nstatic void krkrsdl2_log_flush() {}\nvolatile bool krkrsdl2_engine_teardown_active=false;\n#endif\n#include "SDLTextureUploadState.h"',1)
    s=s.replace('class TVPWindowWindow : public TTVPWindowForm\n{','class TVPWindowWindow : public TTVPWindowForm\n{\n#ifndef __SWITCH__\n\tTVPWindowWindow *hostWindow=nullptr;\n\tstd::vector<uint32_t> uploadShadow;\n\tint uploadShadowW=0, uploadShadowH=0;\n\tTVPSDLTextureUploadState textureUploadState;\n#endif\n')
    s=s.replace('\tg_krkrns_prof.req_notify++;','#ifdef __SWITCH__\n\tg_krkrns_prof.req_notify++;')
    s=s.replace('\tif (this->needsGraphicUpdate) g_krkrns_prof.req_coalesced++;','\tif (this->needsGraphicUpdate) g_krkrns_prof.req_coalesced++;\n#endif',1)
    s=s.replace('\t\tg_krkrns_prof.ev_src[(event.type >> 8) & 15]++;','#ifdef __SWITCH__\n\t\tg_krkrns_prof.ev_src[(event.type >> 8) & 15]++;\n#endif')
    s=s.replace('\tif (win) win->krkrsdl2_dump_layer_tree();','#ifdef __SWITCH__\n\tif (win) win->krkrsdl2_dump_layer_tree();\n#endif')
    s=s.replace('bool TVPWindowWindow::window_receive_event_input(SDL_Event event)\n{','bool TVPWindowWindow::window_receive_event_input(SDL_Event event)\n{\n\tif(getenv("KRKR_INPUT_TRACE") && (event.type==SDL_KEYDOWN || event.type==SDL_KEYUP || event.type==SDL_MOUSEBUTTONDOWN || event.type==SDL_MOUSEBUTTONUP))\n\t\tTVPAddLog(ttstr(TJS_W("HI3798_SDL_INPUT=")) + ttstr((tjs_int)event.type) + TJS_W(",window=") + ttstr((tjs_int)event.window.windowID));\n',1)
    s=s.replace('KRKRNS_LOG("[ns] SDL renderer=%s flags=0x%x max=%dx%d",','TVPAddLog(ttstr(TJS_W("HI3798_SDL_RENDERER=")) + ttstr(renderer_info.name ? renderer_info.name : "?"));\n\t\t\t\t\tKRKRNS_LOG("[ns] SDL renderer=%s flags=0x%x max=%dx%d",',1)
    s=s.replace('SDL_CreateRenderer(this->window, -1, SDL_RENDERER_ACCELERATED | SDL_RENDERER_PRESENTVSYNC)','SDL_CreateRenderer(this->window, -1, getenv("KRKR_SDL_SOFTWARE") ? SDL_RENDERER_SOFTWARE : (SDL_RENDERER_ACCELERATED | SDL_RENDERER_PRESENTVSYNC))',1)
    s=s.replace('void TVPWindowWindow::TickBeat()\n{','void TVPWindowWindow::TickBeat()\n{\n\tstatic int diagnosticFrameStage=0;\n\tif(diagnosticFrameStage<2 && this==_currentWindowWindow && this->isVisible && this->surface && SDL_GetTicks()>(12000+20000*diagnosticFrameStage)) {\n\t\tif(const char* path=getenv("KRKR_FRAME_DUMP")) {\n\t\t\tstd::string file=path; if(diagnosticFrameStage) file += ".late.bmp";\n\t\t\t++diagnosticFrameStage;\n\t\t\tint code=SDL_SaveBMP(this->surface,file.c_str());\n\t\t\tTVPAddLog(ttstr(TJS_W("HI3798_CPU_FRAME=")) + ttstr((tjs_int)this->surface->w) + TJS_W("x") + ttstr((tjs_int)this->surface->h) + TJS_W(",stage=") + ttstr((tjs_int)diagnosticFrameStage) + TJS_W(",result=") + ttstr((tjs_int)code));\n\t\t}\n\t}\n',1)
    s=s.replace('static const bool clickDelayDisabled =\n\t\tTVPIsExistentStorage(ttstr(TJS_W("sdmc:/switch/KRKR-ns/no-click-delay.txt")));','#ifdef __SWITCH__\n\tstatic const bool clickDelayDisabled =\n\t\tTVPIsExistentStorage(ttstr(TJS_W("sdmc:/switch/KRKR-ns/no-click-delay.txt")));\n#else\n\tstatic const bool clickDelayDisabled = false;\n#endif')
    s=s.replace('\t\t\t\tif (krkrsdl2_engine_reinit_wanted)','#ifdef __SWITCH__\n\t\t\t\tif (krkrsdl2_engine_reinit_wanted)',1)
    s=s.replace('\t\t\t\tTVPSystemUninit();','#endif\n\t\t\t\tTVPSystemUninit();',1)
    s=s.replace('static void krkrsdl2_reinitialize_engine()\n{','#ifdef __SWITCH__\nstatic void krkrsdl2_reinitialize_engine()\n{')
    s=s.replace('void krkrsdl2_run_main_loop(void)\n{','#else\nstatic void krkrsdl2_reinitialize_engine() {}\nbool krkrsdl2_take_engine_reinit() { return false; }\n#endif\n\nvoid krkrsdl2_run_main_loop(void)\n{')
    return s
edit('src/core/sdl2/SDLApplication.cpp',sdl_application)
def script_manager(s):
    s=s.replace('TVPAddLog( TVPInfoLoadingStartupScript + TVPStartupScriptName );','extern void TVPHi3798InitFont(); TVPHi3798InitFont();\n\t\t\tTVPAddLog( TVPInfoLoadingStartupScript + TVPStartupScriptName );',1)
    s=s.replace('TVPExecuteStorage(TVPStartupScriptName);','extern bool TVPHi3798PortableStartup();\n\t\t\tif(!TVPHi3798PortableStartup()) TVPExecuteStorage(TVPStartupScriptName);',1)
    for kind in ['eTJS','eTJSScriptError']:
        key='void TVPShowScriptException('+kind+' &e)\n{'
        detail=' + TJS_W("\\ntrace: ") + e.GetTrace()' if kind=='eTJSScriptError' else ''
        s=s.replace(key,key+'\n\tif(getenv("KRKR_BRIEF_ERRORS")) { TVPAddLog(ttstr(TJS_W("HI3798_SCRIPT_ERROR: ")) + e.GetMessage()'+detail+'); TVPTerminateSync(1); return; }\n')
    return s
edit('external/krkrz/base/ScriptMgnIntf.cpp',script_manager)
def colormap_alignment(s):
    # Alpha/blur buffers have byte alignment. A uint32_t* cast promises four
    # bytes of alignment to GCC, which can emit VSTM and SIGBUS on Cortex-A7.
    # memcpy expresses the real contract without disabling the SIMD fast path.
    old='tjs_uint32 s = *(const tjs_uint32*)src;'
    assert s.count(old)==2
    s=s.replace(old,'tjs_uint32 s; memcpy(&s, src, sizeof(s));')
    old='''tjs_uint32 d = *(tjs_uint32 const*)dest;
\t\ttjs_uint32 s = *(tjs_uint32 const*)src;
\t\t*(tjs_uint32*)dest = func( d, s );'''
    assert s.count(old)==1
    return s.replace(old,'''tjs_uint32 d, s;
\t\tmemcpy(&d, dest, sizeof(d));
\t\tmemcpy(&s, src, sizeof(s));
\t\td = func( d, s );
\t\tmemcpy(dest, &d, sizeof(d));''')
edit('external/krkrz/visual/gl/colormap_sse2.cpp',colormap_alignment)
shutil.copy2(Path(__file__).with_name('portable-bootstrap.cpp'),root/'src/core/base/sdl2/Hi3798PortableBootstrap.cpp')
out=args.diff
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(''.join(changes),errors='surrogateescape')
print('Portable source patch:',out)
