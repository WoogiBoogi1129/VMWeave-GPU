from pathlib import Path
R=Path.cwd();O=R/'experiments/ai-passthrough/results/20261026-rodinia-steady';S=O/'src'
p=S/'srad/srad_v2/srad_kernel.cu';s=p.read_text()
for field,arr,cond in [('n','J_cuda','by > 0'),('s','J_cuda','by < gridDim.y-1'),('w','J_cuda','bx > 0'),('e','J_cuda','bx < gridDim.x-1'),('s','C_cuda','by < gridDim.y-1'),('e','C_cuda','bx < gridDim.x-1')]:
 import re
 pattern=r'(^\s*)(\w+\[ty\]\[tx\] = '+arr+r'\[index_'+field+r'\];)'
 s,n=re.subn(pattern,lambda m:m[1]+'if ('+cond+') '+m[2],s,flags=re.M);assert n==1,(field,arr,n)
p.write_text(s)
p=S/'streamcluster/streamcluster_cuda_cpu.cpp';s=p.read_text();s=s.replace('optind=0;exp_elapsed=0;int rc=experiment_main(argc,argv);if(rc)return rc;','optind=0;exp_elapsed=0;int rc=experiment_main(argc,argv);if(rc)return rc;\n FILE *saved=fopen(argv[8],"rb");if(!saved)return 5;fseek(saved,0,SEEK_END);long bytes=ftell(saved);rewind(saved);char*buf=(char*)malloc(bytes);if(fread(buf,1,bytes,saved)!=(size_t)bytes)return 6;fclose(saved);exp_dump(buf,bytes);free(buf);')
p.write_text(s)
