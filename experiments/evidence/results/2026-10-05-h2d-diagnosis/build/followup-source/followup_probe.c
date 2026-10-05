/* Same timed operation as the main sweep, plus separately labelled diagnostics. */
#define main original_main
#include "probe.c"
#undef main
int main(int argc,char **argv){
 if(argc==7 && (!strcmp(argv[1],"patterns")||!strcmp(argv[1],"regression"))){
  int patterns=!strcmp(argv[1],"patterns");
  const char *modes[]={"copy","h2d","copy","copy","copy"};
  const char *sizes[]={"16777216","16777216","4096","65536","1048576"};
  int n=patterns?2:5,shift=0;const char *e=getenv("HD_PATTERN_ORDER");if(e)shift=atoi(e)%2;
  /* Keep the two primary/pattern windows in the same order for ON and OFF.
   * Additional OFF-only regression windows always follow those two. */
  for(int j=0;j<n;j++){int i=j<2?(j+shift)%2:j;char prefix[1024];snprintf(prefix,sizeof(prefix),"%s-%s-%s",argv[5],modes[i],sizes[i]);
   char *a[]={argv[0],(char*)modes[i],(char*)sizes[i],i==0?argv[3]:"10",i==0?argv[4]:"3",prefix,argv[6]};int rc=measure(7,a);if(rc)return rc;
  }return 0;
 }
 return original_main(argc,argv);
}
