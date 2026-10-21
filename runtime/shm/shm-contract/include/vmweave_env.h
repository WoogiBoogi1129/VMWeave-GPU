#ifndef VMWEAVE_ENV_H
#define VMWEAVE_ENV_H
#include <stdlib.h>
#include <string.h>
/* A present canonical value wins, including "0" and the empty string. */
static inline const char *vmweave_getenv(const char *name){
    const char *value=getenv(name);
    if(value || strncmp(name,"VMWEAVE_",8)) return value;
    char legacy[256];size_t n=strlen(name+8);
    if(n>sizeof(legacy)-6) return NULL;
    memcpy(legacy,"FLYT_",5);memcpy(legacy+5,name+8,n+1);
    return getenv(legacy);
}
#endif
