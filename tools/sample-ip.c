/* SPDX-License-Identifier: MIT
 * Minimal read-only userspace IP sampler using Linux perf_event_open.
 * Records are local diagnostic data. No game memory is read or modified.
 */
#define _GNU_SOURCE
#include <linux/perf_event.h>
#include <sys/syscall.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static double seconds(void) {
    struct timespec t; clock_gettime(CLOCK_MONOTONIC,&t);
    return t.tv_sec + t.tv_nsec*1e-9;
}
static void ringcopy(void *dst,const unsigned char *data,size_t size,uint64_t offset,size_t n) {
    size_t pos=offset%size, first=n<size-pos?n:size-pos;
    memcpy(dst,data+pos,first);
    if(first<n) memcpy((char*)dst+first,data,n-first);
}
int main(int argc,char **argv) {
    if(argc!=4) { fprintf(stderr,"usage: sample-ip PID SECONDS OUTPUT\n");return 2; }
    struct perf_event_attr attr; memset(&attr,0,sizeof(attr));
    attr.size=PERF_ATTR_SIZE_VER0;attr.type=PERF_TYPE_SOFTWARE;
    attr.config=PERF_COUNT_SW_CPU_CLOCK;attr.sample_period=4000000;
    attr.sample_type=PERF_SAMPLE_IP;attr.disabled=1;
    attr.exclude_kernel=1;attr.exclude_hv=1;attr.wakeup_events=1;
    int fd=syscall(__NR_perf_event_open,&attr,atoi(argv[1]),-1,-1,0);
    if(fd<0) {perror("perf_event_open");return 1;}
    size_t page=sysconf(_SC_PAGESIZE),size=64*page;
    struct perf_event_mmap_page *meta=mmap(NULL,page+size,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);
    if(meta==MAP_FAILED) {perror("mmap");close(fd);return 1;}
    unsigned char *data=(unsigned char*)meta+page;
    FILE *out=fopen(argv[3],"w");
    if(!out) {perror("output");return 1;}
    unsigned samples=0,lost=0;uint64_t tail=0;
    ioctl(fd,PERF_EVENT_IOC_RESET,0);ioctl(fd,PERF_EVENT_IOC_ENABLE,0);
    double end=seconds()+atoi(argv[2]);
    while(seconds()<end) {
        uint64_t head=meta->data_head; __sync_synchronize();
        while(tail<head) {
            struct perf_event_header h;ringcopy(&h,data,size,tail,sizeof(h));
            if(h.size<sizeof(h) || h.size>size) {fprintf(stderr,"bad record\n");return 1;}
            if(h.type==PERF_RECORD_SAMPLE) {
                uint64_t ip;ringcopy(&ip,data,size,tail+sizeof(h),sizeof(ip));
                fprintf(out,"%llx\n",(unsigned long long)ip);++samples;
            } else if(h.type==PERF_RECORD_LOST) ++lost;
            tail+=h.size;
        }
        __sync_synchronize();meta->data_tail=tail;
        struct timespec delay={0,10000000};nanosleep(&delay,NULL);
    }
    ioctl(fd,PERF_EVENT_IOC_DISABLE,0);fclose(out);munmap(meta,page+size);close(fd);
    fprintf(stderr,"samples=%u lost_records=%u\n",samples,lost);
    return samples?0:1;
}
