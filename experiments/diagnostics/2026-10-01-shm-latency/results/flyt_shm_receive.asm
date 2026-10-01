
/home/ubuntu/taeuk/flyt-k8s-poc-github/.local/performance-20260930/artifacts/libflyt_guest.so:     file format elf64-x86-64


Disassembly of section .init:

Disassembly of section .plt:

Disassembly of section .plt.got:

Disassembly of section .plt.sec:

Disassembly of section .text:

0000000000010160 <flyt_shm_receive>:
   10160:	f3 0f 1e fa          	endbr64
   10164:	41 55                	push   %r13
   10166:	41 54                	push   %r12
   10168:	49 89 f4             	mov    %rsi,%r12
   1016b:	55                   	push   %rbp
   1016c:	48 89 d5             	mov    %rdx,%rbp
   1016f:	53                   	push   %rbx
   10170:	48 89 fb             	mov    %rdi,%rbx
   10173:	48 83 ec 28          	sub    $0x28,%rsp
   10177:	64 48 8b 04 25 28 00 	mov    %fs:0x28,%rax
   1017e:	00 00 
   10180:	48 89 44 24 18       	mov    %rax,0x18(%rsp)
   10185:	31 c0                	xor    %eax,%eax
   10187:	49 89 e5             	mov    %rsp,%r13
   1018a:	66 0f 1f 44 00 00    	nopw   0x0(%rax,%rax,1)
   10190:	66 0f 6f 05 f8 14 00 	movdqa 0x14f8(%rip),%xmm0        # 11690 <_fini+0x1400>
   10197:	00 
   10198:	48 89 ea             	mov    %rbp,%rdx
   1019b:	4c 89 e6             	mov    %r12,%rsi
   1019e:	48 89 df             	mov    %rbx,%rdi
   101a1:	0f 29 04 24          	movaps %xmm0,(%rsp)
   101a5:	e8 e6 36 ff ff       	call   3890 <flyt_shm_try_receive@plt>
   101aa:	83 f8 64             	cmp    $0x64,%eax
   101ad:	75 27                	jne    101d6 <flyt_shm_receive+0x76>
   101af:	31 f6                	xor    %esi,%esi
   101b1:	4c 89 ef             	mov    %r13,%rdi
   101b4:	e8 c7 34 ff ff       	call   3680 <nanosleep@plt>
   101b9:	85 c0                	test   %eax,%eax
   101bb:	74 d3                	je     10190 <flyt_shm_receive+0x30>
   101bd:	e8 ce 33 ff ff       	call   3590 <__errno_location@plt>
   101c2:	83 38 04             	cmpl   $0x4,(%rax)
   101c5:	74 c9                	je     10190 <flyt_shm_receive+0x30>
   101c7:	c7 83 8c 00 00 00 01 	movl   $0x1,0x8c(%rbx)
   101ce:	00 00 00 
   101d1:	b8 07 00 00 00       	mov    $0x7,%eax
   101d6:	48 8b 54 24 18       	mov    0x18(%rsp),%rdx
   101db:	64 48 2b 14 25 28 00 	sub    %fs:0x28,%rdx
   101e2:	00 00 
   101e4:	75 0b                	jne    101f1 <flyt_shm_receive+0x91>
   101e6:	48 83 c4 28          	add    $0x28,%rsp
   101ea:	5b                   	pop    %rbx
   101eb:	5d                   	pop    %rbp
   101ec:	41 5c                	pop    %r12
   101ee:	41 5d                	pop    %r13
   101f0:	c3                   	ret
   101f1:	e8 5a 34 ff ff       	call   3650 <__stack_chk_fail@plt>

Disassembly of section .fini:
