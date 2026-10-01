
/home/ubuntu/taeuk/flyt-k8s-poc-github/.local/performance-20260930/artifacts/libflyt_guest.so:     file format elf64-x86-64


Disassembly of section .init:

Disassembly of section .plt:

Disassembly of section .plt.got:

Disassembly of section .plt.sec:

Disassembly of section .text:

000000000000f510 <flyt_shm_submit>:
    f510:	f3 0f 1e fa          	endbr64
    f514:	41 57                	push   %r15
    f516:	b9 0b 00 00 00       	mov    $0xb,%ecx
    f51b:	41 56                	push   %r14
    f51d:	41 55                	push   %r13
    f51f:	41 54                	push   %r12
    f521:	41 bc 03 00 00 00    	mov    $0x3,%r12d
    f527:	55                   	push   %rbp
    f528:	53                   	push   %rbx
    f529:	48 89 fb             	mov    %rdi,%rbx
    f52c:	48 81 ec 18 01 00 00 	sub    $0x118,%rsp
    f533:	64 48 8b 04 25 28 00 	mov    %fs:0x28,%rax
    f53a:	00 00 
    f53c:	48 89 84 24 08 01 00 	mov    %rax,0x108(%rsp)
    f543:	00 
    f544:	31 c0                	xor    %eax,%eax
    f546:	4c 8d 6c 24 20       	lea    0x20(%rsp),%r13
    f54b:	4c 89 ef             	mov    %r13,%rdi
    f54e:	f3 48 ab             	rep stos %rax,%es:(%rdi)
    f551:	48 85 db             	test   %rbx,%rbx
    f554:	0f 84 b6 02 00 00    	je     f810 <flyt_shm_submit+0x300>
    f55a:	83 bb 88 00 00 00 01 	cmpl   $0x1,0x88(%rbx)
    f561:	0f 85 a9 02 00 00    	jne    f810 <flyt_shm_submit+0x300>
    f567:	48 89 f5             	mov    %rsi,%rbp
    f56a:	e8 61 43 ff ff       	call   38d0 <pthread_self@plt>
    f56f:	48 3b 83 80 00 00 00 	cmp    0x80(%rbx),%rax
    f576:	0f 85 94 02 00 00    	jne    f810 <flyt_shm_submit+0x300>
    f57c:	8b b3 8c 00 00 00    	mov    0x8c(%rbx),%esi
    f582:	8b 83 90 00 00 00    	mov    0x90(%rbx),%eax
    f588:	85 f6                	test   %esi,%esi
    f58a:	0f 85 d0 02 00 00    	jne    f860 <flyt_shm_submit+0x350>
    f590:	85 c0                	test   %eax,%eax
    f592:	0f 85 b8 02 00 00    	jne    f850 <flyt_shm_submit+0x340>
    f598:	48 85 ed             	test   %rbp,%rbp
    f59b:	0f 84 6f 02 00 00    	je     f810 <flyt_shm_submit+0x300>
    f5a1:	48 8b 83 a0 00 00 00 	mov    0xa0(%rbx),%rax
    f5a8:	48 39 45 20          	cmp    %rax,0x20(%rbp)
    f5ac:	0f 85 8e 02 00 00    	jne    f840 <flyt_shm_submit+0x330>
    f5b2:	48 83 f8 ff          	cmp    $0xffffffffffffffff,%rax
    f5b6:	0f 84 84 02 00 00    	je     f840 <flyt_shm_submit+0x330>
    f5bc:	8b 4d 28             	mov    0x28(%rbp),%ecx
    f5bf:	85 c9                	test   %ecx,%ecx
    f5c1:	0f 84 49 02 00 00    	je     f810 <flyt_shm_submit+0x300>
    f5c7:	8b 55 2c             	mov    0x2c(%rbp),%edx
    f5ca:	85 d2                	test   %edx,%edx
    f5cc:	0f 84 3e 02 00 00    	je     f810 <flyt_shm_submit+0x300>
    f5d2:	48 8b 43 50          	mov    0x50(%rbx),%rax
    f5d6:	ba 00 00 00 04       	mov    $0x4000000,%edx
    f5db:	48 8b 4d 38          	mov    0x38(%rbp),%rcx
    f5df:	41 bc 03 00 00 00    	mov    $0x3,%r12d
    f5e5:	48 39 d0             	cmp    %rdx,%rax
    f5e8:	48 0f 47 c2          	cmova  %rdx,%rax
    f5ec:	48 39 c1             	cmp    %rax,%rcx
    f5ef:	0f 87 1b 02 00 00    	ja     f810 <flyt_shm_submit+0x300>
    f5f5:	48 85 c9             	test   %rcx,%rcx
    f5f8:	74 0b                	je     f605 <flyt_shm_submit+0xf5>
    f5fa:	48 83 7d 30 00       	cmpq   $0x0,0x30(%rbp)
    f5ff:	0f 84 0b 02 00 00    	je     f810 <flyt_shm_submit+0x300>
    f605:	48 8b 55 00          	mov    0x0(%rbp),%rdx
    f609:	48 8b 45 08          	mov    0x8(%rbp),%rax
    f60d:	41 bc 04 00 00 00    	mov    $0x4,%r12d
    f613:	48 33 43 68          	xor    0x68(%rbx),%rax
    f617:	48 33 53 60          	xor    0x60(%rbx),%rdx
    f61b:	48 09 d0             	or     %rdx,%rax
    f61e:	0f 85 ec 01 00 00    	jne    f810 <flyt_shm_submit+0x300>
    f624:	48 8b 55 10          	mov    0x10(%rbp),%rdx
    f628:	48 8b 45 18          	mov    0x18(%rbp),%rax
    f62c:	48 33 53 70          	xor    0x70(%rbx),%rdx
    f630:	48 33 43 78          	xor    0x78(%rbx),%rax
    f634:	48 09 d0             	or     %rdx,%rax
    f637:	0f 85 d3 01 00 00    	jne    f810 <flyt_shm_submit+0x300>
    f63d:	48 8b 03             	mov    (%rbx),%rax
    f640:	48 8b 50 40          	mov    0x40(%rax),%rdx
    f644:	48 8b 03             	mov    (%rbx),%rax
    f647:	48 8b 00             	mov    (%rax),%rax
    f64a:	48 3b 43 10          	cmp    0x10(%rbx),%rax
    f64e:	0f 85 1c 02 00 00    	jne    f870 <flyt_shm_submit+0x360>
    f654:	48 3b 53 18          	cmp    0x18(%rbx),%rdx
    f658:	0f 82 12 02 00 00    	jb     f870 <flyt_shm_submit+0x360>
    f65e:	48 39 c2             	cmp    %rax,%rdx
    f661:	0f 87 09 02 00 00    	ja     f870 <flyt_shm_submit+0x360>
    f667:	48 89 c1             	mov    %rax,%rcx
    f66a:	48 29 d1             	sub    %rdx,%rcx
    f66d:	48 83 f9 01          	cmp    $0x1,%rcx
    f671:	0f 87 f9 01 00 00    	ja     f870 <flyt_shm_submit+0x360>
    f677:	48 83 f8 ff          	cmp    $0xffffffffffffffff,%rax
    f67b:	0f 84 ef 01 00 00    	je     f870 <flyt_shm_submit+0x360>
    f681:	48 89 53 18          	mov    %rdx,0x18(%rbx)
    f685:	48 39 c2             	cmp    %rax,%rdx
    f688:	0f 85 c2 01 00 00    	jne    f850 <flyt_shm_submit+0x340>
    f68e:	48 8d 74 24 10       	lea    0x10(%rsp),%rsi
    f693:	bf 01 00 00 00       	mov    $0x1,%edi
    f698:	e8 53 3f ff ff       	call   35f0 <clock_gettime@plt>
    f69d:	41 89 c4             	mov    %eax,%r12d
    f6a0:	85 c0                	test   %eax,%eax
    f6a2:	0f 85 e0 01 00 00    	jne    f888 <flyt_shm_submit+0x378>
    f6a8:	48 8b 4c 24 10       	mov    0x10(%rsp),%rcx
    f6ad:	48 85 c9             	test   %rcx,%rcx
    f6b0:	0f 88 d2 01 00 00    	js     f888 <flyt_shm_submit+0x378>
    f6b6:	48 bf 53 5a 9b a0 2f 	movabs $0x44b82fa09b5a53,%rdi
    f6bd:	b8 44 00 
    f6c0:	48 8b 74 24 18       	mov    0x18(%rsp),%rsi
    f6c5:	48 89 f2             	mov    %rsi,%rdx
    f6c8:	48 f7 d2             	not    %rdx
    f6cb:	48 c1 ea 09          	shr    $0x9,%rdx
    f6cf:	48 89 d0             	mov    %rdx,%rax
    f6d2:	48 f7 e7             	mul    %rdi
    f6d5:	48 c1 ea 0b          	shr    $0xb,%rdx
    f6d9:	48 39 d1             	cmp    %rdx,%rcx
    f6dc:	0f 87 a6 01 00 00    	ja     f888 <flyt_shm_submit+0x378>
    f6e2:	8b 83 94 00 00 00    	mov    0x94(%rbx),%eax
    f6e8:	48 69 c9 00 ca 9a 3b 	imul   $0x3b9aca00,%rcx,%rcx
    f6ef:	48 69 c0 40 42 0f 00 	imul   $0xf4240,%rax,%rax
    f6f6:	48 01 f1             	add    %rsi,%rcx
    f6f9:	48 01 c8             	add    %rcx,%rax
    f6fc:	48 89 44 24 08       	mov    %rax,0x8(%rsp)
    f701:	0f 82 81 01 00 00    	jb     f888 <flyt_shm_submit+0x378>
    f707:	f3 0f 6f 4b 60       	movdqu 0x60(%rbx),%xmm1
    f70c:	f3 0f 6f 53 70       	movdqu 0x70(%rbx),%xmm2
    f711:	b8 01 00 00 00       	mov    $0x1,%eax
    f716:	4c 8b 7d 20          	mov    0x20(%rbp),%r15
    f71a:	4c 8b 75 28          	mov    0x28(%rbp),%r14
    f71e:	66 89 44 24 20       	mov    %ax,0x20(%rsp)
    f723:	48 8b 55 38          	mov    0x38(%rbp),%rdx
    f727:	0f 11 4c 24 22       	movups %xmm1,0x22(%rsp)
    f72c:	4c 89 7c 24 48       	mov    %r15,0x48(%rsp)
    f731:	4c 89 74 24 60       	mov    %r14,0x60(%rsp)
    f736:	48 89 54 24 58       	mov    %rdx,0x58(%rsp)
    f73b:	0f 11 54 24 32       	movups %xmm2,0x32(%rsp)
    f740:	48 85 d2             	test   %rdx,%rdx
    f743:	0f 85 54 01 00 00    	jne    f89d <flyt_shm_submit+0x38d>
    f749:	4c 89 b3 98 00 00 00 	mov    %r14,0x98(%rbx)
    f750:	66 49 0f 6e c7       	movq   %r15,%xmm0
    f755:	4c 89 ee             	mov    %r13,%rsi
    f758:	48 8d bc 24 80 00 00 	lea    0x80(%rsp),%rdi
    f75f:	00 
    f760:	c7 83 90 00 00 00 01 	movl   $0x1,0x90(%rbx)
    f767:	00 00 00 
    f76a:	0f 16 44 24 08       	movhps 0x8(%rsp),%xmm0
    f76f:	0f 11 83 a8 00 00 00 	movups %xmm0,0xa8(%rbx)
    f776:	e8 b5 f0 ff ff       	call   e830 <encode>
    f77b:	8b 43 08             	mov    0x8(%rbx),%eax
    f77e:	66 0f 6f 9c 24 80 00 	movdqa 0x80(%rsp),%xmm3
    f785:	00 00 
    f787:	66 0f 6f a4 24 90 00 	movdqa 0x90(%rsp),%xmm4
    f78e:	00 00 
    f790:	66 0f 6f ac 24 a0 00 	movdqa 0xa0(%rsp),%xmm5
    f797:	00 00 
    f799:	66 0f 6f b4 24 b0 00 	movdqa 0xb0(%rsp),%xmm6
    f7a0:	00 00 
    f7a2:	83 e8 01             	sub    $0x1,%eax
    f7a5:	48 23 43 10          	and    0x10(%rbx),%rax
    f7a9:	66 0f 6f bc 24 c0 00 	movdqa 0xc0(%rsp),%xmm7
    f7b0:	00 00 
    f7b2:	48 83 c0 01          	add    $0x1,%rax
    f7b6:	48 c1 e0 07          	shl    $0x7,%rax
    f7ba:	48 03 03             	add    (%rbx),%rax
    f7bd:	0f 11 18             	movups %xmm3,(%rax)
    f7c0:	66 0f 6f 9c 24 d0 00 	movdqa 0xd0(%rsp),%xmm3
    f7c7:	00 00 
    f7c9:	0f 11 60 10          	movups %xmm4,0x10(%rax)
    f7cd:	66 0f 6f a4 24 e0 00 	movdqa 0xe0(%rsp),%xmm4
    f7d4:	00 00 
    f7d6:	0f 11 68 20          	movups %xmm5,0x20(%rax)
    f7da:	66 0f 6f ac 24 f0 00 	movdqa 0xf0(%rsp),%xmm5
    f7e1:	00 00 
    f7e3:	0f 11 70 30          	movups %xmm6,0x30(%rax)
    f7e7:	0f 11 78 40          	movups %xmm7,0x40(%rax)
    f7eb:	0f 11 58 50          	movups %xmm3,0x50(%rax)
    f7ef:	0f 11 60 60          	movups %xmm4,0x60(%rax)
    f7f3:	0f 11 68 70          	movups %xmm5,0x70(%rax)
    f7f7:	48 8b 43 10          	mov    0x10(%rbx),%rax
    f7fb:	48 8b 13             	mov    (%rbx),%rdx
    f7fe:	48 83 c0 01          	add    $0x1,%rax
    f802:	48 89 43 10          	mov    %rax,0x10(%rbx)
    f806:	48 89 02             	mov    %rax,(%rdx)
    f809:	0f 1f 80 00 00 00 00 	nopl   0x0(%rax)
    f810:	48 8b 84 24 08 01 00 	mov    0x108(%rsp),%rax
    f817:	00 
    f818:	64 48 2b 04 25 28 00 	sub    %fs:0x28,%rax
    f81f:	00 00 
    f821:	0f 85 88 00 00 00    	jne    f8af <flyt_shm_submit+0x39f>
    f827:	48 81 c4 18 01 00 00 	add    $0x118,%rsp
    f82e:	44 89 e0             	mov    %r12d,%eax
    f831:	5b                   	pop    %rbx
    f832:	5d                   	pop    %rbp
    f833:	41 5c                	pop    %r12
    f835:	41 5d                	pop    %r13
    f837:	41 5e                	pop    %r14
    f839:	41 5f                	pop    %r15
    f83b:	c3                   	ret
    f83c:	0f 1f 40 00          	nopl   0x0(%rax)
    f840:	41 bc 03 00 00 00    	mov    $0x3,%r12d
    f846:	eb c8                	jmp    f810 <flyt_shm_submit+0x300>
    f848:	0f 1f 84 00 00 00 00 	nopl   0x0(%rax,%rax,1)
    f84f:	00 
    f850:	41 bc 05 00 00 00    	mov    $0x5,%r12d
    f856:	eb b8                	jmp    f810 <flyt_shm_submit+0x300>
    f858:	0f 1f 84 00 00 00 00 	nopl   0x0(%rax,%rax,1)
    f85f:	00 
    f860:	83 f8 01             	cmp    $0x1,%eax
    f863:	41 bc 06 00 00 00    	mov    $0x6,%r12d
    f869:	41 83 dc ff          	sbb    $0xffffffff,%r12d
    f86d:	eb a1                	jmp    f810 <flyt_shm_submit+0x300>
    f86f:	90                   	nop
    f870:	c7 83 8c 00 00 00 01 	movl   $0x1,0x8c(%rbx)
    f877:	00 00 00 
    f87a:	41 bc 03 00 00 00    	mov    $0x3,%r12d
    f880:	eb 8e                	jmp    f810 <flyt_shm_submit+0x300>
    f882:	66 0f 1f 44 00 00    	nopw   0x0(%rax,%rax,1)
    f888:	c7 83 8c 00 00 00 01 	movl   $0x1,0x8c(%rbx)
    f88f:	00 00 00 
    f892:	41 bc 08 00 00 00    	mov    $0x8,%r12d
    f898:	e9 73 ff ff ff       	jmp    f810 <flyt_shm_submit+0x300>
    f89d:	48 8b 7b 40          	mov    0x40(%rbx),%rdi
    f8a1:	48 8b 75 30          	mov    0x30(%rbp),%rsi
    f8a5:	e8 f6 3e ff ff       	call   37a0 <memcpy@plt>
    f8aa:	e9 9a fe ff ff       	jmp    f749 <flyt_shm_submit+0x239>
    f8af:	e8 9c 3d ff ff       	call   3650 <__stack_chk_fail@plt>

Disassembly of section .fini:
