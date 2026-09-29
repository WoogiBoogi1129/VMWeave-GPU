"""Move an ELF64 section table to EOF for the legacy Flyt size calculation.

Flyt cuModuleLoadData infers buffer size as e_shoff + e_shnum*e_shentsize.
CUDA 12.8 ptxas puts program headers AFTER that position. Relocating only
section-table bytes to EOF preserves every section, segment and kernel byte,
and lets the original unmodified Flyt reader include the entire file.
"""
import argparse,hashlib,json,struct
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('output',type=Path);p.add_argument('--manifest',type=Path,required=True);a=p.parse_args()
s=a.input.read_bytes();assert s[:6]==b'\x7fELF\x02\x01';off=struct.unpack_from('<Q',s,40)[0];width,count=struct.unpack_from('<HH',s,58);table=s[off:off+width*count];assert len(table)==width*count
pad=(-len(s))%8;new=bytearray(s+b'\0'*pad+table);struct.pack_into('<Q',new,40,len(s)+pad)
assert new[:40]==s[:40] and new[48:len(s)]==s[48:] and new[-len(table):]==table
a.output.write_bytes(new);a.manifest.write_text(json.dumps({'input_sha256':hashlib.sha256(s).hexdigest(),'output_sha256':hashlib.sha256(new).hexdigest(),'original_bytes':len(s),'normalized_bytes':len(new),'original_section_table_offset':off,'new_section_table_offset':len(s)+pad,'kernel_and_segment_bytes_unchanged':True,'reason':'Legacy Flyt infers image extent from end of section table; ptxas puts program headers after original table.'},indent=2)+'\n')
