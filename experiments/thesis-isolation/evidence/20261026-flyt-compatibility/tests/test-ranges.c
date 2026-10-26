#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include "resource-map.h"
int main(void) {
 resource_map *m=init_resource_map(2), *other=init_resource_map(2), *handles=init_resource_map(2);
 void *a,*b,*c,*h; char x[128], y[128];
 assert(!resource_map_add_range(m,x,NULL,16,&a));
 assert(resource_map_get_addr(m,a)==x);
 assert(resource_map_get_addr(m,(char*)a+4)==x+4);
 assert(resource_map_get_addr(m,(char*)a+15)==x+15);
 assert(!resource_map_contains(m,(char*)a+16));
 assert(!resource_map_contains(m,(char*)a-1));
 assert(!resource_map_contains(other,a));
 assert(!resource_map_add_range(m,y,NULL,128,&b));
 assert(resource_map_get_addr(m,(char*)a+4)==x+4);
 assert(resource_map_get_addr(m,(char*)b+127)==y+127);
 resource_map_unset(m,(char*)a+1); assert(resource_map_contains(m,a));
 resource_map_unset(m,a); assert(!resource_map_contains(m,a));
 assert(!resource_map_add_range(m,x,NULL,32,&c)); assert(c==x && c!=b);
 assert(resource_map_get_addr(m,c)==x);
 struct {int n; void *p[2];} nested={2,{c,(char*)c+4}};
 assert(nested.p[0]==x && nested.p[1]==x+4);
 assert(resource_map_add_range(m,x,NULL,UINT64_MAX,&a)==-1);
 assert(!resource_map_add(handles,x,NULL,&h)); assert(resource_map_get_addr(handles,h)==x);
 assert(!resource_map_contains(handles,0)); assert(!resource_map_get(handles,(void*)UINT64_MAX));
 resource_map_unset(handles,h); assert(!resource_map_contains(handles,h));
 resource_map_iter *it=resource_map_init_iter(m); int n=0; while(resource_map_iter_next(it))++n; assert(n==2);
 resource_map_free_iter(it); free_resource_map(m); free_resource_map(other); free_resource_map(handles);
 puts("range mapping tests PASS");
}
