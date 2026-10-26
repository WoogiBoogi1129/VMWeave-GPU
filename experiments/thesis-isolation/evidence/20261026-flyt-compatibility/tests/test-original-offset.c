#include <stdio.h>
#include <stdint.h>
#include "resource-map.h"
int main(void){char x[16];void *p;resource_map *m=init_resource_map(16);resource_map_add(m,x,NULL,&p);printf("{\"base_resolves\":%s,\"offset_4_resolves\":%s}\n",resource_map_get_addr(m,p)==x?"true":"false",resource_map_get_addr(m,(void*)((uintptr_t)p+4))==x+4?"true":"false");return 0;}
