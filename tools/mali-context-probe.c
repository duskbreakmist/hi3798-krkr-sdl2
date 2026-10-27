/* SPDX-License-Identifier: MIT
 * Independent EGL/GLES2 pbuffer probe. No native window, framebuffer, DirectFB
 * initialization outside the explicitly selected dummy backend, SDL, VO or
 * hardware display-control API is called by this program.
 * All graphics entry points come from the explicitly selected private library.
 * Vendor fbdev libraries may open the framebuffer for queries; inspect their
 * system calls rather than assuming pbuffer initialization never opens it.
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/resource.h>
#ifdef PROBE_WITH_DIRECTFB
#include <directfb.h>
#endif
typedef void *EDisplay;
typedef void *EConfig;
typedef void *EContext;
typedef void *ESurface;
typedef int EInt;
typedef unsigned EBool;
typedef unsigned GEnum;
typedef unsigned GUint;
typedef int GInt;

#define EGL_NONE 0x3038
#define EGL_SURFACE_TYPE 0x3033
#define EGL_PBUFFER_BIT 1
#define EGL_RENDERABLE_TYPE 0x3040
#define EGL_OPENGL_ES2_BIT 4
#define EGL_OPENGL_ES_API 0x30a0
#define EGL_CONTEXT_CLIENT_VERSION 0x3098
#define EGL_WIDTH 0x3057
#define EGL_HEIGHT 0x3056
#define GL_VERTEX_SHADER 0x8b31
#define GL_FRAGMENT_SHADER 0x8b30

#define PROC(ret,name,args) static ret (*name) args
PROC(EDisplay,eglGetDisplay,(void*));
PROC(EBool,eglInitialize,(EDisplay,EInt*,EInt*));
PROC(const char*,eglQueryString,(EDisplay,EInt));
PROC(EBool,eglGetConfigs,(EDisplay,EConfig*,EInt,EInt*));
PROC(EBool,eglGetConfigAttrib,(EDisplay,EConfig,EInt,EInt*));
PROC(EBool,eglBindAPI,(unsigned));
PROC(EContext,eglCreateContext,(EDisplay,EConfig,EContext,const EInt*));
PROC(ESurface,eglCreatePbufferSurface,(EDisplay,EConfig,const EInt*));
PROC(EBool,eglMakeCurrent,(EDisplay,ESurface,ESurface,EContext));
PROC(EBool,eglDestroySurface,(EDisplay,ESurface));
PROC(EBool,eglDestroyContext,(EDisplay,EContext));
PROC(EBool,eglTerminate,(EDisplay));
PROC(EInt,eglGetError,(void));
PROC(const unsigned char*,glGetString,(GEnum));
PROC(GUint,glCreateShader,(GEnum));
PROC(void,glShaderSource,(GUint,GInt,const char*const*,const GInt*));
PROC(void,glCompileShader,(GUint));
PROC(void,glGetShaderiv,(GUint,GEnum,GInt*));
PROC(void,glGetShaderInfoLog,(GUint,GInt,GInt*,char*));
PROC(GUint,glCreateProgram,(void));
PROC(void,glAttachShader,(GUint,GUint));
PROC(void,glBindAttribLocation,(GUint,GUint,const char*));
PROC(void,glLinkProgram,(GUint));
PROC(void,glGetProgramiv,(GUint,GEnum,GInt*));
PROC(void,glUseProgram,(GUint));
PROC(void,glViewport,(GInt,GInt,GInt,GInt));
PROC(void,glClearColor,(float,float,float,float));
PROC(void,glClear,(GEnum));
PROC(void,glEnableVertexAttribArray,(GUint));
PROC(void,glVertexAttribPointer,(GUint,GInt,GEnum,unsigned char,GInt,const void*));
PROC(void,glDrawArrays,(GEnum,GInt,GInt));
PROC(void,glFinish,(void));
PROC(void,glReadPixels,(GInt,GInt,GInt,GInt,GEnum,GEnum,void*));
PROC(GEnum,glGetError,(void));
PROC(void,glDeleteShader,(GUint));
PROC(void,glDeleteProgram,(GUint));

static void *library;
static int load(void *target,const char *name) {
    void *symbol=dlsym(library,name);
    if(!symbol){fprintf(stderr,"MISSING=%s:%s\n",name,dlerror());return 0;}
    memcpy(target,&symbol,sizeof(symbol));return 1;
}
#define LOAD(name) do{if(!load(&name,#name))goto done;}while(0)
static GUint shader(GEnum kind,const char *source) {
    GUint s=glCreateShader(kind);GInt ok=0;
    glShaderSource(s,1,&source,NULL);glCompileShader(s);glGetShaderiv(s,0x8b81,&ok);
    if(!ok){char log[1024]={0};glGetShaderInfoLog(s,1023,NULL,log);fprintf(stderr,"SHADER_ERROR=%s\n",log);}
    return ok?s:0;
}
static int channel_tolerance(int bits) {
    if(bits>=8)return 1;
    if(bits<=0)return 255;
    return 255/(2*((1<<bits)-1))+2;
}
int main(int argc,char **argv) {
    setvbuf(stdout,NULL,_IONBF,0);
    struct rlimit core={0,0};setrlimit(RLIMIT_CORE,&core);
    int rc=1,initialized=0,current=0;
    int red_bits=8,green_bits=8,blue_bits=8;
    EDisplay display=NULL;EContext context=NULL;ESurface surface=NULL;
    void *native_display=NULL;
#ifdef PROBE_WITH_DIRECTFB
    IDirectFB *dfb=NULL;
    IDirectFBDisplayLayer *layer=NULL;
#endif
    if(argc!=2 && !(argc==4 && !strcmp(argv[2],"--dfb-dummy"))){
        fprintf(stderr,"usage: mali-context-probe LIB [--dfb-dummy PRIVATE_MODULE_DIR]\n");return 2;
    }
    library=dlopen(argv[1],RTLD_NOW|RTLD_GLOBAL);
    if(!library){fprintf(stderr,"DLOPEN_FAIL=%s\n",dlerror());return 1;}
    puts("DLOPEN=PASS");
    LOAD(eglGetDisplay);LOAD(eglInitialize);LOAD(eglQueryString);LOAD(eglGetConfigs);
    LOAD(eglGetConfigAttrib);LOAD(eglBindAPI);LOAD(eglCreateContext);LOAD(eglCreatePbufferSurface);
    LOAD(eglMakeCurrent);LOAD(eglDestroySurface);LOAD(eglDestroyContext);LOAD(eglTerminate);LOAD(eglGetError);
    if(argc==4) {
#ifdef PROBE_WITH_DIRECTFB
        DFBResult (*dfInit)(int*,char***);
        DFBResult (*dfOption)(const char*,const char*);
        DFBResult (*dfCreate)(IDirectFB**);
        if(!load(&dfInit,"DirectFBInit")||!load(&dfOption,"DirectFBSetOption")||!load(&dfCreate,"DirectFBCreate"))goto done;
        setenv("DFBARGS","system=dummy,no-sighandler",1);
        int count=1;char app[]="mali-dummy-probe";char *arguments[]={app,NULL};char **args=arguments;
        DFBResult result=dfInit(&count,&args);printf("DFB_INIT=%d\n",result);if(result)goto done;
        result=dfOption("system","dummy");if(result)goto done;
        result=dfOption("module-dir",argv[3]);printf("DFB_PRIVATE_MODULES=%d\n",result);if(result)goto done;
        result=dfCreate(&dfb);printf("DFB_CREATE=%d\n",result);if(result)goto done;
        result=dfb->GetDisplayLayer(dfb,DLID_PRIMARY,&layer);printf("DFB_GET_LAYER=%d\n",result);if(result)goto done;
        result=layer->SetCooperativeLevel(layer,DLSCL_ADMINISTRATIVE);if(result)goto done;
        DFBDisplayLayerConfig config;memset(&config,0,sizeof(config));
        config.flags=DLCONF_WIDTH|DLCONF_HEIGHT|DLCONF_PIXELFORMAT;
        config.width=64;config.height=64;config.pixelformat=DSPF_ARGB;
        result=layer->SetConfiguration(layer,&config);printf("DFB_DUMMY_CONFIG=%d\n",result);if(result)goto done;
        native_display=layer;
        puts("NATIVE_DISPLAY=real DirectFBDisplayLayer from dummy backend");
#else
        puts("DUMMY_MODE_NOT_COMPILED");goto done;
#endif
    }
    if(!eglBindAPI(EGL_OPENGL_ES_API)){printf("BIND_API_FAIL=0x%x\n",eglGetError());goto done;}
    puts("CALL=eglGetDisplay");
    display=eglGetDisplay(native_display);
    if(!display){printf("GET_DISPLAY_FAIL=0x%x\n",eglGetError());goto done;}
    EInt major=0,minor=0;
    puts("CALL=eglInitialize");
    if(!eglInitialize(display,&major,&minor)){printf("INITIALIZE_FAIL=0x%x\n",eglGetError());goto done;}
    initialized=1;printf("EGL_VERSION=%d.%d\n",major,minor);
    printf("EGL_VENDOR=%s\n",eglQueryString(display,0x3053));
    printf("EGL_EXTENSIONS=%s\n",eglQueryString(display,0x3055));
    EInt n=0;
    if(!eglGetConfigs(display,NULL,0,&n)){printf("GET_CONFIGS_FAIL=0x%x\n",eglGetError());goto done;}
    printf("CONFIG_COUNT=%d\n",n);
    if(n<=0 || n>1024)goto done;
    EConfig *configs=calloc(n,sizeof(*configs));
    if(!configs)goto done;
    if(!eglGetConfigs(display,configs,n,&n)){free(configs);goto done;}
    if(!eglBindAPI(EGL_OPENGL_ES_API)){free(configs);goto done;}
    for(int attempt=0;attempt<2*n;++attempt) {
        int i=attempt%n;
        EInt type=0,render=0,red=0,green=0,blue=0;
        eglGetConfigAttrib(display,configs[i],EGL_SURFACE_TYPE,&type);
        eglGetConfigAttrib(display,configs[i],EGL_RENDERABLE_TYPE,&render);
        eglGetConfigAttrib(display,configs[i],0x3024,&red);
        eglGetConfigAttrib(display,configs[i],0x3023,&green);
        eglGetConfigAttrib(display,configs[i],0x3022,&blue);
        int wide=(red>=8&&green>=8&&blue>=8);
        if((attempt<n)!=wide)continue;
        printf("CONFIG=%d surface=0x%x render=0x%x rgb=%d,%d,%d\n",i,type,render,red,green,blue);
        if(!(render&EGL_OPENGL_ES2_BIT)||red<=0||green<=0||blue<=0)continue;
        EInt ca[]={EGL_CONTEXT_CLIENT_VERSION,2,EGL_NONE};
        context=eglCreateContext(display,configs[i],NULL,ca);
        if(!context){printf("CREATE_CONTEXT_FAIL=%d:0x%x\n",i,eglGetError());continue;}
        if(!(type&EGL_PBUFFER_BIT)) {
            printf("CONTEXT_CREATED_NO_PBUFFER=%d\n",i);
            eglDestroyContext(display,context);context=NULL;continue;
        }
        EInt sa[]={EGL_WIDTH,64,EGL_HEIGHT,64,EGL_NONE};
        surface=eglCreatePbufferSurface(display,configs[i],sa);
        if(surface){red_bits=red;green_bits=green;blue_bits=blue;break;}
        printf("CREATE_PBUFFER_FAIL=%d:0x%x\n",i,eglGetError());
        eglDestroyContext(display,context);context=NULL;
    }
    free(configs);
    if(!context||!surface)goto done;
    if(!eglMakeCurrent(display,surface,surface,context)){printf("MAKE_CURRENT_FAIL=0x%x\n",eglGetError());goto done;}
    current=1;
    printf("SELECTED_RGB_BITS=%d,%d,%d\n",red_bits,green_bits,blue_bits);
    LOAD(glGetString);LOAD(glCreateShader);LOAD(glShaderSource);LOAD(glCompileShader);
    LOAD(glGetShaderiv);LOAD(glGetShaderInfoLog);LOAD(glCreateProgram);LOAD(glAttachShader);
    LOAD(glBindAttribLocation);LOAD(glLinkProgram);LOAD(glGetProgramiv);LOAD(glUseProgram);
    LOAD(glViewport);LOAD(glClearColor);LOAD(glClear);LOAD(glEnableVertexAttribArray);
    LOAD(glVertexAttribPointer);LOAD(glDrawArrays);LOAD(glFinish);LOAD(glReadPixels);
    LOAD(glGetError);LOAD(glDeleteShader);LOAD(glDeleteProgram);
    printf("GL_VENDOR=%s\nGL_RENDERER=%s\nGL_VERSION=%s\n",glGetString(0x1f00),glGetString(0x1f01),glGetString(0x1f02));
    glViewport(0,0,64,64);
    glClearColor(0.125f,0.25f,0.5f,1.0f);glClear(0x4000);glFinish();
    unsigned char clear[4]={0};glReadPixels(0,0,1,1,0x1908,0x1401,clear);
    printf("FLOAT_API_PIXEL=%u,%u,%u,%u\n",clear[0],clear[1],clear[2],clear[3]);
    if(abs((int)clear[0]-32)>channel_tolerance(red_bits) ||
       abs((int)clear[1]-64)>channel_tolerance(green_bits) ||
       abs((int)clear[2]-128)>channel_tolerance(blue_bits) || clear[3]!=255)goto done;
    GUint vs=shader(GL_VERTEX_SHADER,"attribute vec2 p; void main(){gl_Position=vec4(p,0.0,1.0);}");
    GUint fs=shader(GL_FRAGMENT_SHADER,"precision mediump float; void main(){gl_FragColor=vec4(0.25,0.5,0.75,1.0);}");
    if(!vs||!fs)goto done;
    GUint program=glCreateProgram();glAttachShader(program,vs);glAttachShader(program,fs);
    glBindAttribLocation(program,0,"p");glLinkProgram(program);GInt linked=0;
    glGetProgramiv(program,0x8b82,&linked);if(!linked)goto done;
    glUseProgram(program);glViewport(0,0,64,64);
    glClearColor(0,0,0,0);glClear(0x4000);
    const float vertices[]={-1,-1,3,-1,-1,3};
    glEnableVertexAttribArray(0);glVertexAttribPointer(0,2,0x1406,0,0,vertices);
    glDrawArrays(4,0,3);glFinish();
    unsigned char pixels[64*64*4];glReadPixels(0,0,64,64,0x1908,0x1401,pixels);
    GEnum error=glGetError();int bad=0;
    for(unsigned i=0;i<64*64;++i) {
        unsigned char *p=pixels+4*i;
        if(abs((int)p[0]-64)>channel_tolerance(red_bits) ||
           abs((int)p[1]-128)>channel_tolerance(green_bits) ||
           abs((int)p[2]-191)>channel_tolerance(blue_bits) || p[3]!=255)++bad;
    }
    printf("PIXEL=%u,%u,%u,%u BAD_PIXELS=%d GL_ERROR=0x%x\n",pixels[0],pixels[1],pixels[2],pixels[3],bad,error);
    rc=bad||error?1:0;
    glDeleteProgram(program);glDeleteShader(vs);glDeleteShader(fs);
done:
    if(initialized) {
        if(current){puts("CLEANUP=unbind");eglMakeCurrent(display,NULL,NULL,NULL);}
        if(surface)eglDestroySurface(display,surface);
        if(context)eglDestroyContext(display,context);
        puts("CLEANUP=eglTerminate");
        eglTerminate(display);
    }
#ifdef PROBE_WITH_DIRECTFB
    if(layer){puts("CLEANUP=layer release");layer->Release(layer);}
    if(dfb){puts("CLEANUP=DirectFB release");dfb->Release(dfb);}
#endif
    if(library){puts("CLEANUP=dlclose");dlclose(library);}
    printf("RESULT=%d\n",rc);return rc;
}
