
/home/ubuntu/taeuk/flyt-k8s-poc-github/.local/performance-20260930/artifacts/libflyt_guest.so:     file format elf64-x86-64


Disassembly of section .init:

Disassembly of section .plt:

Disassembly of section .plt.got:

Disassembly of section .plt.sec:

Disassembly of section .text:

000000000000f8c0 <flyt_shm_worker_take>:
    f8c0:	f3 0f 1e fa          	endbr64
    f8c4:	41 57                	push   %r15
    f8c6:	41 56                	push   %r14
    f8c8:	41 55                	push   %r13
    f8ca:	41 54                	push   %r12
    f8cc:	55                   	push   %rbp
    f8cd:	53                   	push   %rbx
    f8ce:	48 83 ec 68          	sub    $0x68,%rsp
    f8d2:	64 48 8b 04 25 28 00 	mov    %fs:0x28,%rax
    f8d9:	00 00 
    f8db:	48 89 44 24 58       	mov    %rax,0x58(%rsp)
    f8e0:	31 c0                	xor    %eax,%eax
    f8e2:	48 85 ff             	test   %rdi,%rdi
    f8e5:	0f 84 75 01 00 00    	je     fa60 <flyt_shm_worker_take+0x1a0>
    f8eb:	83 bf 88 00 00 00 02 	cmpl   $0x2,0x88(%rdi)
    f8f2:	48 89 fb             	mov    %rdi,%rbx
    f8f5:	41 bc 03 00 00 00    	mov    $0x3,%r12d
    f8fb:	0f 85 8f 00 00 00    	jne    f990 <flyt_shm_worker_take+0xd0>
    f901:	48 89 f5             	mov    %rsi,%rbp
    f904:	e8 c7 3f ff ff       	call   38d0 <pthread_self@plt>
    f909:	48 3b 83 80 00 00 00 	cmp    0x80(%rbx),%rax
    f910:	75 7e                	jne    f990 <flyt_shm_worker_take+0xd0>
    f912:	8b 93 8c 00 00 00    	mov    0x8c(%rbx),%edx
    f918:	85 d2                	test   %edx,%edx
    f91a:	0f 85 28 01 00 00    	jne    fa48 <flyt_shm_worker_take+0x188>
    f920:	48 85 ed             	test   %rbp,%rbp
    f923:	74 6b                	je     f990 <flyt_shm_worker_take+0xd0>
    f925:	66 0f ef c0          	pxor   %xmm0,%xmm0
    f929:	0f 11 45 00          	movups %xmm0,0x0(%rbp)
    f92d:	0f 11 45 10          	movups %xmm0,0x10(%rbp)
    f931:	0f 11 45 20          	movups %xmm0,0x20(%rbp)
    f935:	0f 11 45 30          	movups %xmm0,0x30(%rbp)
    f939:	8b 83 90 00 00 00    	mov    0x90(%rbx),%eax
    f93f:	85 c0                	test   %eax,%eax
    f941:	75 45                	jne    f988 <flyt_shm_worker_take+0xc8>
    f943:	48 8b 43 20          	mov    0x20(%rbx),%rax
    f947:	48 8b 50 40          	mov    0x40(%rax),%rdx
    f94b:	48 8b 43 20          	mov    0x20(%rbx),%rax
    f94f:	48 8b 08             	mov    (%rax),%rcx
    f952:	48 8b 43 30          	mov    0x30(%rbx),%rax
    f956:	48 39 c1             	cmp    %rax,%rcx
    f959:	75 65                	jne    f9c0 <flyt_shm_worker_take+0x100>
    f95b:	48 3b 53 38          	cmp    0x38(%rbx),%rdx
    f95f:	72 5f                	jb     f9c0 <flyt_shm_worker_take+0x100>
    f961:	48 39 c2             	cmp    %rax,%rdx
    f964:	77 5a                	ja     f9c0 <flyt_shm_worker_take+0x100>
    f966:	48 89 c1             	mov    %rax,%rcx
    f969:	48 29 d1             	sub    %rdx,%rcx
    f96c:	48 83 f9 01          	cmp    $0x1,%rcx
    f970:	77 4e                	ja     f9c0 <flyt_shm_worker_take+0x100>
    f972:	48 83 f8 ff          	cmp    $0xffffffffffffffff,%rax
    f976:	74 48                	je     f9c0 <flyt_shm_worker_take+0x100>
    f978:	48 89 53 38          	mov    %rdx,0x38(%rbx)
    f97c:	48 39 c2             	cmp    %rax,%rdx
    f97f:	74 57                	je     f9d8 <flyt_shm_worker_take+0x118>
    f981:	0f 1f 80 00 00 00 00 	nopl   0x0(%rax)
    f988:	41 bc 64 00 00 00    	mov    $0x64,%r12d
    f98e:	66 90                	xchg   %ax,%ax
    f990:	48 8b 44 24 58       	mov    0x58(%rsp),%rax
    f995:	64 48 2b 04 25 28 00 	sub    %fs:0x28,%rax
    f99c:	00 00 
    f99e:	0f 85 b6 01 00 00    	jne    fb5a <flyt_shm_worker_take+0x29a>
    f9a4:	48 83 c4 68          	add    $0x68,%rsp
    f9a8:	44 89 e0             	mov    %r12d,%eax
    f9ab:	5b                   	pop    %rbx
    f9ac:	5d                   	pop    %rbp
    f9ad:	41 5c                	pop    %r12
    f9af:	41 5d                	pop    %r13
    f9b1:	41 5e                	pop    %r14
    f9b3:	41 5f                	pop    %r15
    f9b5:	c3                   	ret
    f9b6:	66 2e 0f 1f 84 00 00 	cs nopw 0x0(%rax,%rax,1)
    f9bd:	00 00 00 
    f9c0:	c7 83 8c 00 00 00 01 	movl   $0x1,0x8c(%rbx)
    f9c7:	00 00 00 
    f9ca:	41 bc 03 00 00 00    	mov    $0x3,%r12d
    f9d0:	eb be                	jmp    f990 <flyt_shm_worker_take+0xd0>
    f9d2:	66 0f 1f 44 00 00    	nopw   0x0(%rax,%rax,1)
    f9d8:	48 89 e6             	mov    %rsp,%rsi
    f9db:	48 89 df             	mov    %rbx,%rdi
    f9de:	e8 0d f2 ff ff       	call   ebf0 <peek>
    f9e3:	41 89 c4             	mov    %eax,%r12d
    f9e6:	85 c0                	test   %eax,%eax
    f9e8:	0f 85 5a 01 00 00    	jne    fb48 <flyt_shm_worker_take+0x288>
    f9ee:	48 8b 44 24 0a       	mov    0xa(%rsp),%rax
    f9f3:	48 8b 54 24 02       	mov    0x2(%rsp),%rdx
    f9f8:	48 33 43 68          	xor    0x68(%rbx),%rax
    f9fc:	48 33 53 60          	xor    0x60(%rbx),%rdx
    fa00:	48 09 d0             	or     %rdx,%rax
    fa03:	75 2b                	jne    fa30 <flyt_shm_worker_take+0x170>
    fa05:	48 8b 44 24 1a       	mov    0x1a(%rsp),%rax
    fa0a:	48 8b 54 24 12       	mov    0x12(%rsp),%rdx
    fa0f:	48 33 43 78          	xor    0x78(%rbx),%rax
    fa13:	48 33 53 70          	xor    0x70(%rbx),%rdx
    fa17:	48 09 d0             	or     %rdx,%rax
    fa1a:	75 14                	jne    fa30 <flyt_shm_worker_take+0x170>
    fa1c:	66 83 3c 24 01       	cmpw   $0x1,(%rsp)
    fa21:	74 4d                	je     fa70 <flyt_shm_worker_take+0x1b0>
    fa23:	41 bc 03 00 00 00    	mov    $0x3,%r12d
    fa29:	eb 0b                	jmp    fa36 <flyt_shm_worker_take+0x176>
    fa2b:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)
    fa30:	41 bc 04 00 00 00    	mov    $0x4,%r12d
    fa36:	c7 83 8c 00 00 00 01 	movl   $0x1,0x8c(%rbx)
    fa3d:	00 00 00 
    fa40:	e9 4b ff ff ff       	jmp    f990 <flyt_shm_worker_take+0xd0>
    fa45:	0f 1f 00             	nopl   (%rax)
    fa48:	83 bb 90 00 00 00 01 	cmpl   $0x1,0x90(%rbx)
    fa4f:	41 bc 06 00 00 00    	mov    $0x6,%r12d
    fa55:	41 83 dc ff          	sbb    $0xffffffff,%r12d
    fa59:	e9 32 ff ff ff       	jmp    f990 <flyt_shm_worker_take+0xd0>
    fa5e:	66 90                	xchg   %ax,%ax
    fa60:	41 bc 03 00 00 00    	mov    $0x3,%r12d
    fa66:	e9 25 ff ff ff       	jmp    f990 <flyt_shm_worker_take+0xd0>
    fa6b:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)
    fa70:	4c 8b 7c 24 28       	mov    0x28(%rsp),%r15
    fa75:	4c 3b bb a0 00 00 00 	cmp    0xa0(%rbx),%r15
    fa7c:	0f 85 3e ff ff ff    	jne    f9c0 <flyt_shm_worker_take+0x100>
    fa82:	4c 8b 6c 24 38       	mov    0x38(%rsp),%r13
    fa87:	49 81 fd 00 00 00 04 	cmp    $0x4000000,%r13
    fa8e:	0f 87 2c ff ff ff    	ja     f9c0 <flyt_shm_worker_take+0x100>
    fa94:	4c 8b 74 24 30       	mov    0x30(%rsp),%r14
    fa99:	48 8b 43 50          	mov    0x50(%rbx),%rax
    fa9d:	49 39 c6             	cmp    %rax,%r14
    faa0:	0f 87 1a ff ff ff    	ja     f9c0 <flyt_shm_worker_take+0x100>
    faa6:	4c 29 f0             	sub    %r14,%rax
    faa9:	49 39 c5             	cmp    %rax,%r13
    faac:	0f 87 0e ff ff ff    	ja     f9c0 <flyt_shm_worker_take+0x100>
    fab2:	4d 85 ed             	test   %r13,%r13
    fab5:	0f 84 9b 00 00 00    	je     fb56 <flyt_shm_worker_take+0x296>
    fabb:	4c 89 ef             	mov    %r13,%rdi
    fabe:	e8 6d 3d ff ff       	call   3830 <malloc@plt>
    fac3:	48 85 c0             	test   %rax,%rax
    fac6:	0f 84 93 00 00 00    	je     fb5f <flyt_shm_worker_take+0x29f>
    facc:	31 d2                	xor    %edx,%edx
    face:	4c 03 73 40          	add    0x40(%rbx),%r14
    fad2:	66 0f 1f 44 00 00    	nopw   0x0(%rax,%rax,1)
    fad8:	49 8d 0c 16          	lea    (%r14,%rdx,1),%rcx
    fadc:	0f b6 09             	movzbl (%rcx),%ecx
    fadf:	88 0c 10             	mov    %cl,(%rax,%rdx,1)
    fae2:	48 83 c2 01          	add    $0x1,%rdx
    fae6:	49 39 d5             	cmp    %rdx,%r13
    fae9:	75 ed                	jne    fad8 <flyt_shm_worker_take+0x218>
    faeb:	48 8b 54 24 40       	mov    0x40(%rsp),%rdx
    faf0:	f3 0f 6f 4c 24 02    	movdqu 0x2(%rsp),%xmm1
    faf6:	48 89 45 30          	mov    %rax,0x30(%rbp)
    fafa:	48 8b 43 10          	mov    0x10(%rbx),%rax
    fafe:	f3 0f 6f 54 24 12    	movdqu 0x12(%rsp),%xmm2
    fb04:	4c 89 7d 20          	mov    %r15,0x20(%rbp)
    fb08:	48 89 55 28          	mov    %rdx,0x28(%rbp)
    fb0c:	48 83 c0 01          	add    $0x1,%rax
    fb10:	4c 89 6d 38          	mov    %r13,0x38(%rbp)
    fb14:	0f 11 4d 00          	movups %xmm1,0x0(%rbp)
    fb18:	0f 11 55 10          	movups %xmm2,0x10(%rbp)
    fb1c:	48 89 93 98 00 00 00 	mov    %rdx,0x98(%rbx)
    fb23:	48 8b 13             	mov    (%rbx),%rdx
    fb26:	4c 89 bb a8 00 00 00 	mov    %r15,0xa8(%rbx)
    fb2d:	c7 83 90 00 00 00 01 	movl   $0x1,0x90(%rbx)
    fb34:	00 00 00 
    fb37:	48 89 43 10          	mov    %rax,0x10(%rbx)
    fb3b:	48 89 42 40          	mov    %rax,0x40(%rdx)
    fb3f:	e9 4c fe ff ff       	jmp    f990 <flyt_shm_worker_take+0xd0>
    fb44:	0f 1f 40 00          	nopl   0x0(%rax)
    fb48:	83 f8 64             	cmp    $0x64,%eax
    fb4b:	0f 85 e5 fe ff ff    	jne    fa36 <flyt_shm_worker_take+0x176>
    fb51:	e9 3a fe ff ff       	jmp    f990 <flyt_shm_worker_take+0xd0>
    fb56:	31 c0                	xor    %eax,%eax
    fb58:	eb 91                	jmp    faeb <flyt_shm_worker_take+0x22b>
    fb5a:	e8 f1 3a ff ff       	call   3650 <__stack_chk_fail@plt>
    fb5f:	41 bc 08 00 00 00    	mov    $0x8,%r12d
    fb65:	e9 26 fe ff ff       	jmp    f990 <flyt_shm_worker_take+0xd0>

Disassembly of section .fini:
