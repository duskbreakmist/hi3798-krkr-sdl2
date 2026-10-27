// Linux/ARM probe bootstrap for the pinned krkr-ns engine.
// This adds a launch path only; no game class or animation behavior is faked.
#include "tjsCommHead.h"
#include "ScriptMgnIntf.h"
#include "StorageIntf.h"
#include "SysInitImpl.h"
#include "DebugIntf.h"
#include "StringUtil.h"
#include "CharacterSet.h"
#include "TextStream.h"
#include <filesystem>
#include <algorithm>
#include <vector>
#include <cstdlib>

extern void TVPSetXP3FilterScript(const ttstr& content);
extern bool TVPAddFontToFreeType(const ttstr&, std::vector<tjs_string>*);
static ttstr ToStorage(const std::string& path) {
    tjs_string text;
    if (!TVPUtf8ToUtf16(text,path)) throw eTJSError(TJS_W("Invalid UTF-8 project path"));
    return TVPNormalizeStorageName(ttstr(text));
}

void TVPHi3798InitFont() {
    const char* font=std::getenv("KRKR_FONT_FILE");
    if (font && *font) {
        if(!TVPAddFontToFreeType(ToStorage(font),nullptr))
            throw eTJSError(TJS_W("Cannot load private probe font"));
        TVPAddLog(TJS_W("HI3798_SDL2_FONT_READY"));
    }
    const char* menu=std::getenv("KRKR_MENU_SCRIPT");
    if (menu && *menu) {
        TVPExecuteStorage(ToStorage(menu));
        TVPAddLog(TJS_W("HI3798_SDL2_MENU_MODEL_READY"));
    }
}

bool TVPHi3798PortableStartup() {
    const char* requested=std::getenv("KRKR_PROJECT");
    if (!requested || !*requested) return false;
    namespace fs=std::filesystem;
    const fs::path entry=fs::absolute(requested);
    if (!fs::is_regular_file(entry)) throw eTJSError(TJS_W("Missing selected game archive"));
    const fs::path directory=entry.parent_path();
    TVPProjectDir=ToStorage(directory.string()+"/");
    tjs_string nativeDirectory;
    TVPUtf8ToUtf16(nativeDirectory,directory.string()+"/");
    TVPNativeProjectDir=nativeDirectory;
    TVPSetCurrentDirectory(TVPProjectDir);
    TVPSetCommandLine(TJS_W("-debugwin"),TJS_W("no"));
    ttstr filter;
    const ttstr filterPath=ToStorage((directory/"xp3filter.tjs").string());
    if (fs::is_regular_file(directory/"xp3filter.tjs")) {
        auto* stream=TVPCreateTextStreamForRead(filterPath,TJS_W(""));
        try { stream->Read(filter,0); } catch (...) { delete stream; throw; }
        delete stream;
    }
    TVPSetXP3FilterScript(filter);
    TVPAddLog(TJS_W("HI3798_SDL2_FILTER_READY"));
    if (fs::is_regular_file(directory/"patch.tjs")) {
        TVPAddLog(TJS_W("HI3798_SDL2_PATCH_BEGIN"));
        TVPExecuteStorage(ToStorage((directory/"patch.tjs").string()));
        TVPAddLog(TJS_W("HI3798_SDL2_PATCH_END"));
    }
    std::vector<fs::path> archives;
    const char* archiveMode=std::getenv("KRKR_ARCHIVE_MODE");
    const bool gameMountsArchives=archiveMode && std::string(archiveMode)=="game";
    if(!gameMountsArchives)
        for (const auto& item:fs::directory_iterator(directory))
            if (item.is_regular_file() && item.path().extension()==".xp3" && item.path()!=entry)
                archives.push_back(item.path());
    std::sort(archives.begin(),archives.end());
    archives.push_back(entry);
    for (const auto& archive:archives) TVPAddAutoPath(ToStorage(archive.string())+TJS_W(">"));
    TVPAddLog(gameMountsArchives ? TJS_W("HI3798_ARCHIVE_MODE=game") : TJS_W("HI3798_ARCHIVE_MODE=preload"));
    TVPExecuteScript(TJS_W(
        "if(typeof(global.debugwin)==\"undefined\") global.debugwin=0;\n"
        "if(typeof(global.inXP3archivePacked)==\"undefined\") global.inXP3archivePacked=1;\n"
        "if(typeof(global.convertMode)==\"undefined\") global.convertMode=0;\n"
        "if(typeof(global.debugWindowEnabled)==\"undefined\") global.debugWindowEnabled=0;\n"));
    TVPStartupScriptName=ToStorage(entry.string())+TJS_W(">startup.tjs");
    TVPAddLog(TJS_W("HI3798_SDL2_GAME_START"));
    TVPExecuteStorage(TVPStartupScriptName);
    return true;
}
