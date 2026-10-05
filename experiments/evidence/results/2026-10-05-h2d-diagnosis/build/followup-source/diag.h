#ifndef HD_DIAG_H
#define HD_DIAG_H
#include <stdint.h>
#include <stddef.h>
int hd_variant(void);
void hd_set_scatter(const void *p);
const void *hd_scatter(void);
uint64_t hd_now(void);
void hd_record(unsigned stage,uint64_t id,size_t bytes,uint64_t start);
void hd_pack_record(uint64_t id,size_t bytes,uint64_t start,uint64_t end);
void hd_dump(const char *role);
void hd_set_id(uint64_t id);
uint64_t hd_id(void);
void *hd_alloc(size_t n);
void hd_free(void *p);
void hd_cleanup(void);
#endif
