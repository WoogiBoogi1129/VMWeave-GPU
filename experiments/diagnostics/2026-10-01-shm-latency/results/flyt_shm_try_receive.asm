
/home/ubuntu/taeuk/flyt-k8s-poc-github/.local/performance-20260930/artifacts/libflyt_guest.so:     file format elf64-x86-64


Disassembly of section .init:

Disassembly of section .plt:

Disassembly of section .plt.got:

Disassembly of section .plt.sec:

Disassembly of section .text:

000000000000fe90 <flyt_shm_try_receive>:
    fe90:	f3 0f 1e fa          	endbr64
    fe94:	41 55                	push   %r13
    fe96:	41 54                	push   %r12
    fe98:	55                   	push   %rbp
    fe99:	53                   	push   %rbx
    fe9a:	48 83 ec 78          	sub    $0x78,%rsp
    fe9e:	64 48 8b 04 25 28 00 	mov    %fs:0x28,%rax
    fea5:	00 00 
    fea7:	48 89 44 24 68       	mov    %rax,0x68(%rsp)
    feac:	31 c0                	xor    %eax,%eax
    feae:	48 85 ff             	test   %rdi,%rdi
    feb1:	0f 84 b1 01 00 00    	je     10068 <flyt_shm_try_receive+0x1d8>
    feb7:	83 bf 88 00 00 00 01 	cmpl   $0x1,0x88(%rdi)
    febe:	48 89 fb             	mov    %rdi,%rbx
    fec1:	41 bd 03 00 00 00    	mov    $0x3,%r13d
    fec7:	0f 85 43 01 00 00    	jne    10010 <flyt_shm_try_receive+0x180>
    fecd:	49 89 f4             	mov    %rsi,%r12
    fed0:	48 89 d5             	mov    %rdx,%rbp
    fed3:	e8 f8 39 ff ff       	call   38d0 <pthread_self@plt>
    fed8:	48 3b 83 80 00 00 00 	cmp    0x80(%rbx),%rax
    fedf:	0f 85 2b 01 00 00    	jne    10010 <flyt_shm_try_receive+0x180>
    fee5:	8b 93 8c 00 00 00    	mov    0x8c(%rbx),%edx
    feeb:	85 d2                	test   %edx,%edx
    feed:	0f 85 05 01 00 00    	jne    fff8 <flyt_shm_try_receive+0x168>
    fef3:	48 85 ed             	test   %rbp,%rbp
    fef6:	0f 84 14 01 00 00    	je     10010 <flyt_shm_try_receive+0x180>
    fefc:	8b 83 90 00 00 00    	mov    0x90(%rbx),%eax
    ff02:	85 c0                	test   %eax,%eax
    ff04:	0f 84 06 01 00 00    	je     10010 <flyt_shm_try_receive+0x180>
    ff0a:	4c 39 a3 a8 00 00 00 	cmp    %r12,0xa8(%rbx)
    ff11:	0f 85 f9 00 00 00    	jne    10010 <flyt_shm_try_receive+0x180>
    ff17:	48 c7 45 20 00 00 00 	movq   $0x0,0x20(%rbp)
    ff1e:	00 
    ff1f:	48 89 e6             	mov    %rsp,%rsi
    ff22:	bf 01 00 00 00       	mov    $0x1,%edi
    ff27:	48 c7 45 00 00 00 00 	movq   $0x0,0x0(%rbp)
    ff2e:	00 
    ff2f:	c7 45 08 00 00 00 00 	movl   $0x0,0x8(%rbp)
    ff36:	e8 b5 36 ff ff       	call   35f0 <clock_gettime@plt>
    ff3b:	85 c0                	test   %eax,%eax
    ff3d:	0f 85 f5 00 00 00    	jne    10038 <flyt_shm_try_receive+0x1a8>
    ff43:	48 8b 0c 24          	mov    (%rsp),%rcx
    ff47:	48 85 c9             	test   %rcx,%rcx
    ff4a:	0f 88 e8 00 00 00    	js     10038 <flyt_shm_try_receive+0x1a8>
    ff50:	48 bf 53 5a 9b a0 2f 	movabs $0x44b82fa09b5a53,%rdi
    ff57:	b8 44 00 
    ff5a:	48 8b 74 24 08       	mov    0x8(%rsp),%rsi
    ff5f:	48 89 f2             	mov    %rsi,%rdx
    ff62:	48 f7 d2             	not    %rdx
    ff65:	48 c1 ea 09          	shr    $0x9,%rdx
    ff69:	48 89 d0             	mov    %rdx,%rax
    ff6c:	48 f7 e7             	mul    %rdi
    ff6f:	48 c1 ea 0b          	shr    $0xb,%rdx
    ff73:	48 39 d1             	cmp    %rdx,%rcx
    ff76:	0f 87 bc 00 00 00    	ja     10038 <flyt_shm_try_receive+0x1a8>
    ff7c:	48 69 c9 00 ca 9a 3b 	imul   $0x3b9aca00,%rcx,%rcx
    ff83:	48 01 f1             	add    %rsi,%rcx
    ff86:	48 39 8b b0 00 00 00 	cmp    %rcx,0xb0(%rbx)
    ff8d:	0f 86 a5 00 00 00    	jbe    10038 <flyt_shm_try_receive+0x1a8>
    ff93:	48 8d 74 24 10       	lea    0x10(%rsp),%rsi
    ff98:	48 8d 7b 20          	lea    0x20(%rbx),%rdi
    ff9c:	e8 4f ec ff ff       	call   ebf0 <peek>
    ffa1:	41 89 c5             	mov    %eax,%r13d
    ffa4:	85 c0                	test   %eax,%eax
    ffa6:	0f 85 9c 01 00 00    	jne    10148 <flyt_shm_try_receive+0x2b8>
    ffac:	48 8b 44 24 1a       	mov    0x1a(%rsp),%rax
    ffb1:	48 8b 54 24 12       	mov    0x12(%rsp),%rdx
    ffb6:	48 33 43 68          	xor    0x68(%rbx),%rax
    ffba:	48 33 53 60          	xor    0x60(%rbx),%rdx
    ffbe:	48 09 d0             	or     %rdx,%rax
    ffc1:	0f 85 89 00 00 00    	jne    10050 <flyt_shm_try_receive+0x1c0>
    ffc7:	48 8b 44 24 2a       	mov    0x2a(%rsp),%rax
    ffcc:	48 8b 54 24 22       	mov    0x22(%rsp),%rdx
    ffd1:	48 33 43 78          	xor    0x78(%rbx),%rax
    ffd5:	48 33 53 70          	xor    0x70(%rbx),%rdx
    ffd9:	48 09 d0             	or     %rdx,%rax
    ffdc:	75 72                	jne    10050 <flyt_shm_try_receive+0x1c0>
    ffde:	66 83 7c 24 10 02    	cmpw   $0x2,0x10(%rsp)
    ffe4:	0f 84 86 00 00 00    	je     10070 <flyt_shm_try_receive+0x1e0>
    ffea:	41 bd 03 00 00 00    	mov    $0x3,%r13d
    fff0:	eb 64                	jmp    10056 <flyt_shm_try_receive+0x1c6>
    fff2:	66 0f 1f 44 00 00    	nopw   0x0(%rax,%rax,1)
    fff8:	83 bb 90 00 00 00 01 	cmpl   $0x1,0x90(%rbx)
    ffff:	41 bd 06 00 00 00    	mov    $0x6,%r13d
   10005:	41 83 dd ff          	sbb    $0xffffffff,%r13d
   10009:	0f 1f 80 00 00 00 00 	nopl   0x0(%rax)
   10010:	48 8b 44 24 68       	mov    0x68(%rsp),%rax
   10015:	64 48 2b 04 25 28 00 	sub    %fs:0x28,%rax
   1001c:	00 00 
   1001e:	0f 85 32 01 00 00    	jne    10156 <flyt_shm_try_receive+0x2c6>
   10024:	48 83 c4 78          	add    $0x78,%rsp
   10028:	44 89 e8             	mov    %r13d,%eax
   1002b:	5b                   	pop    %rbx
   1002c:	5d                   	pop    %rbp
   1002d:	41 5c                	pop    %r12
   1002f:	41 5d                	pop    %r13
   10031:	c3                   	ret
   10032:	66 0f 1f 44 00 00    	nopw   0x0(%rax,%rax,1)
   10038:	c7 83 8c 00 00 00 01 	movl   $0x1,0x8c(%rbx)
   1003f:	00 00 00 
   10042:	41 bd 07 00 00 00    	mov    $0x7,%r13d
   10048:	eb c6                	jmp    10010 <flyt_shm_try_receive+0x180>
   1004a:	66 0f 1f 44 00 00    	nopw   0x0(%rax,%rax,1)
   10050:	41 bd 04 00 00 00    	mov    $0x4,%r13d
   10056:	c7 83 8c 00 00 00 01 	movl   $0x1,0x8c(%rbx)
   1005d:	00 00 00 
   10060:	eb ae                	jmp    10010 <flyt_shm_try_receive+0x180>
   10062:	66 0f 1f 44 00 00    	nopw   0x0(%rax,%rax,1)
   10068:	41 bd 03 00 00 00    	mov    $0x3,%r13d
   1006e:	eb a0                	jmp    10010 <flyt_shm_try_receive+0x180>
   10070:	48 8b 83 a8 00 00 00 	mov    0xa8(%rbx),%rax
   10077:	48 39 44 24 38       	cmp    %rax,0x38(%rsp)
   1007c:	0f 85 ae 00 00 00    	jne    10130 <flyt_shm_try_receive+0x2a0>
   10082:	48 8b 83 98 00 00 00 	mov    0x98(%rbx),%rax
   10089:	48 39 44 24 50       	cmp    %rax,0x50(%rsp)
   1008e:	0f 85 9c 00 00 00    	jne    10130 <flyt_shm_try_receive+0x2a0>
   10094:	48 8b 54 24 48       	mov    0x48(%rsp),%rdx
   10099:	48 81 fa 00 00 00 04 	cmp    $0x4000000,%rdx
   100a0:	0f 87 8a 00 00 00    	ja     10130 <flyt_shm_try_receive+0x2a0>
   100a6:	48 8b 4c 24 40       	mov    0x40(%rsp),%rcx
   100ab:	48 8b 43 58          	mov    0x58(%rbx),%rax
   100af:	48 39 c1             	cmp    %rax,%rcx
   100b2:	77 7c                	ja     10130 <flyt_shm_try_receive+0x2a0>
   100b4:	48 29 c8             	sub    %rcx,%rax
   100b7:	48 39 c2             	cmp    %rax,%rdx
   100ba:	77 74                	ja     10130 <flyt_shm_try_receive+0x2a0>
   100bc:	48 89 55 20          	mov    %rdx,0x20(%rbp)
   100c0:	48 3b 55 18          	cmp    0x18(%rbp),%rdx
   100c4:	77 a2                	ja     10068 <flyt_shm_try_receive+0x1d8>
   100c6:	48 85 d2             	test   %rdx,%rdx
   100c9:	74 29                	je     100f4 <flyt_shm_try_receive+0x264>
   100cb:	48 8b 7d 10          	mov    0x10(%rbp),%rdi
   100cf:	48 85 ff             	test   %rdi,%rdi
   100d2:	74 94                	je     10068 <flyt_shm_try_receive+0x1d8>
   100d4:	31 c0                	xor    %eax,%eax
   100d6:	48 03 4b 48          	add    0x48(%rbx),%rcx
   100da:	66 0f 1f 44 00 00    	nopw   0x0(%rax,%rax,1)
   100e0:	48 8d 34 01          	lea    (%rcx,%rax,1),%rsi
   100e4:	0f b6 36             	movzbl (%rsi),%esi
   100e7:	40 88 34 07          	mov    %sil,(%rdi,%rax,1)
   100eb:	48 83 c0 01          	add    $0x1,%rax
   100ef:	48 39 c2             	cmp    %rax,%rdx
   100f2:	75 ec                	jne    100e0 <flyt_shm_try_receive+0x250>
   100f4:	48 8b 44 24 58       	mov    0x58(%rsp),%rax
   100f9:	48 8b 53 20          	mov    0x20(%rbx),%rdx
   100fd:	48 89 45 00          	mov    %rax,0x0(%rbp)
   10101:	8b 44 24 60          	mov    0x60(%rsp),%eax
   10105:	89 45 08             	mov    %eax,0x8(%rbp)
   10108:	48 8b 43 30          	mov    0x30(%rbx),%rax
   1010c:	48 83 c0 01          	add    $0x1,%rax
   10110:	48 89 43 30          	mov    %rax,0x30(%rbx)
   10114:	48 89 42 40          	mov    %rax,0x40(%rdx)
   10118:	c7 83 90 00 00 00 00 	movl   $0x0,0x90(%rbx)
   1011f:	00 00 00 
   10122:	48 83 83 a0 00 00 00 	addq   $0x1,0xa0(%rbx)
   10129:	01 
   1012a:	e9 e1 fe ff ff       	jmp    10010 <flyt_shm_try_receive+0x180>
   1012f:	90                   	nop
   10130:	c7 83 8c 00 00 00 01 	movl   $0x1,0x8c(%rbx)
   10137:	00 00 00 
   1013a:	41 bd 03 00 00 00    	mov    $0x3,%r13d
   10140:	e9 cb fe ff ff       	jmp    10010 <flyt_shm_try_receive+0x180>
   10145:	0f 1f 00             	nopl   (%rax)
   10148:	83 f8 64             	cmp    $0x64,%eax
   1014b:	0f 85 05 ff ff ff    	jne    10056 <flyt_shm_try_receive+0x1c6>
   10151:	e9 ba fe ff ff       	jmp    10010 <flyt_shm_try_receive+0x180>
   10156:	e8 f5 34 ff ff       	call   3650 <__stack_chk_fail@plt>

Disassembly of section .fini:
