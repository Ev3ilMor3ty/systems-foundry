// Minimal executable containers. No assembler, linker or SDK is invoked.
fn put(b: &mut [u8], at: usize, n: u64, size: usize) {
    b[at..at + size].copy_from_slice(&n.to_le_bytes()[..size]);
}
fn align(n: usize, a: usize) -> usize {
    (n + a - 1) & !(a - 1)
}

pub fn elf(code: &[u8]) -> Vec<u8> {
    let mut file = vec![0; 4096];
    file[..7].copy_from_slice(b"\x7fELF\x02\x01\x01");
    put(&mut file, 16, 2, 2);
    put(&mut file, 18, 62, 2);
    put(&mut file, 20, 1, 4);
    put(&mut file, 24, 0x401000, 8);
    put(&mut file, 32, 64, 8);
    put(&mut file, 52, 64, 2);
    put(&mut file, 54, 56, 2);
    put(&mut file, 56, 2, 2);
    put(&mut file, 64, 1, 4);
    put(&mut file, 68, 5, 4); // RX PT_LOAD
    put(&mut file, 80, 0x400000, 8);
    put(&mut file, 88, 0x400000, 8);
    put(&mut file, 96, (4096 + code.len()) as u64, 8);
    put(&mut file, 104, (4096 + code.len()) as u64, 8);
    put(&mut file, 112, 4096, 8);
    put(&mut file, 120, 0x6474e551, 4);
    put(&mut file, 124, 6, 4);
    put(&mut file, 168, 16, 8); // GNU_STACK RW
    file.extend_from_slice(code);
    file
}

pub fn pe(code: &[u8]) -> Vec<u8> {
    let text_size = align(code.len(), 512);
    let idata_rva = align(0x1000 + code.len(), 4096);
    let mut imports = vec![0; 104];
    let dll = imports.len();
    imports.extend_from_slice(b"KERNEL32.dll\0");
    if imports.len() % 2 != 0 {
        imports.push(0);
    }
    let mut hints = Vec::new();
    for name in ["GetStdHandle", "WriteFile", "ExitProcess"] {
        hints.push(imports.len());
        imports.extend_from_slice(&[0, 0]);
        imports.extend_from_slice(name.as_bytes());
        imports.push(0);
        if imports.len() % 2 != 0 {
            imports.push(0);
        }
    }
    put(&mut imports, 0, (idata_rva + 40) as u64, 4);
    put(&mut imports, 12, (idata_rva + dll) as u64, 4);
    put(&mut imports, 16, (idata_rva + 72) as u64, 4);
    for (i, hint) in hints.iter().enumerate() {
        for base in [40, 72] {
            put(&mut imports, base + 8 * i, (idata_rva + hint) as u64, 8);
        }
    }
    let mut file = vec![0; 512];
    file[..2].copy_from_slice(b"MZ");
    put(&mut file, 0x3c, 0x80, 4);
    file[0x80..0x84].copy_from_slice(b"PE\0\0");
    let coff = 0x84;
    put(&mut file, coff, 0x8664, 2);
    put(&mut file, coff + 2, 2, 2);
    put(&mut file, coff + 16, 240, 2);
    put(&mut file, coff + 18, 0x22, 2);
    let opt = coff + 20;
    put(&mut file, opt, 0x20b, 2);
    put(&mut file, opt + 4, text_size as u64, 4);
    put(&mut file, opt + 8, align(imports.len(), 512) as u64, 4);
    put(&mut file, opt + 16, 0x1000, 4);
    put(&mut file, opt + 20, 0x1000, 4);
    put(&mut file, opt + 24, 0x140000000, 8);
    put(&mut file, opt + 32, 4096, 4);
    put(&mut file, opt + 36, 512, 4);
    put(&mut file, opt + 40, 6, 2);
    put(&mut file, opt + 48, 6, 2);
    put(
        &mut file,
        opt + 56,
        align(idata_rva + imports.len(), 4096) as u64,
        4,
    );
    put(&mut file, opt + 60, 512, 4);
    put(&mut file, opt + 68, 3, 2);
    put(&mut file, opt + 70, 0x8100, 2);
    put(&mut file, opt + 72, 1024 * 1024, 8);
    put(&mut file, opt + 80, 4096, 8);
    put(&mut file, opt + 88, 1024 * 1024, 8);
    put(&mut file, opt + 96, 4096, 8);
    put(&mut file, opt + 108, 16, 4);
    put(&mut file, opt + 120, idata_rva as u64, 4);
    put(&mut file, opt + 124, 40, 4);
    put(&mut file, opt + 112 + 12 * 8, (idata_rva + 72) as u64, 4);
    put(&mut file, opt + 116 + 12 * 8, 32, 4);
    let section = opt + 240;
    file[section..section + 5].copy_from_slice(b".text");
    put(&mut file, section + 8, code.len() as u64, 4);
    put(&mut file, section + 12, 0x1000, 4);
    put(&mut file, section + 16, text_size as u64, 4);
    put(&mut file, section + 20, 512, 4);
    put(&mut file, section + 36, 0x60000020, 4);
    let section = section + 40;
    file[section..section + 6].copy_from_slice(b".idata");
    put(&mut file, section + 8, imports.len() as u64, 4);
    put(&mut file, section + 12, idata_rva as u64, 4);
    put(&mut file, section + 16, align(imports.len(), 512) as u64, 4);
    put(&mut file, section + 20, (512 + text_size) as u64, 4);
    put(&mut file, section + 36, 0xc0000040, 4);
    file.extend_from_slice(code);
    file.resize(512 + text_size, 0);
    file.extend_from_slice(&imports);
    file.resize(512 + text_size + align(imports.len(), 512), 0);
    file
}
