---
name: android-boot-image-repack-mtk
description: Extracting ramdisk from ANDROID! boot images (header v0/v1/v2) and repacking with mkbootimg for MediaTek MT6761/X657B — including separate DTB vs appended DTB approaches
source: auto-skill
extracted_at: '2026-06-03T04:52:07.738Z'
---

# Android Boot Image Repacking for MediaTek MT67xx

## Extracting Ramdisk from Stock Boot Image

### Header Parsing (all versions)

Android boot image headers share a common first 40 bytes, then diverge:

```
Offset  Size  Field
0       8     magic ("ANDROID!")
8       4     kernel_size (LE u32)
12      4     kernel_addr (LE u32)
16      4     ramdisk_size (LE u32)
20      4     ramdisk_addr (LE u32)
24      4     second_size (LE u32)
28      4     second_addr (LE u32)
32      4     tags_addr (LE u32)
36      4     page_size (LE u32)
40      4     header_version (LE u32)
```

After offset 40:
- **v0/v1**: header = page_size bytes (typically 2048), cmdline at offset 64, 512 bytes
- **v2**: header occupies one page (2048 bytes on X657B); `recovery_dtbo_size` is at offset 1632, `recovery_dtbo_offset` at 1636 (LE u64), `header_size` at 1644, `dtb_size` at 1648, and `dtb_addr` at 1652 (LE u64). The v2 header struct ends at byte 1660.

### Python Extraction Script

```python
import struct

def extract_boot_image(img_path, ramdisk_out_path):
    with open(img_path, 'rb') as f:
        f.seek(0)
        hdr = f.read(64)

        magic = hdr[0:8]
        assert magic == b'ANDROID!', f'Not ANDROID!: {magic}'

        kernel_size  = struct.unpack_from('<I', hdr, 8)[0]
        ramdisk_size = struct.unpack_from('<I', hdr, 16)[0]
        page_size    = struct.unpack_from('<I', hdr, 36)[0]

        f.seek(40)
        header_version = struct.unpack('<I', f.read(4))[0]

        if header_version > 2:
            raise NotImplementedError('This extractor handles boot header versions 0, 1, and 2 only')
        # v0/v1/v2 occupy one page; X657B v2 uses a 2048-byte page.
        header_len = page_size
        header_pages = 1

        # Kernel offset = after header, page-aligned
        kernel_offset = header_pages * page_size

        # Ramdisk offset = after kernel, page-aligned
        ramdisk_pages = (kernel_size + page_size - 1) // page_size
        ramdisk_offset = kernel_offset + ramdisk_pages * page_size

        f.seek(ramdisk_offset)
        ramdisk_data = f.read(ramdisk_size)

        with open(ramdisk_out_path, 'wb') as rf:
            rf.write(ramdisk_data)

        # For v2: also extract dtb
        if header_version >= 2:
            f.seek(0)
            full_hdr = f.read(header_len)
            dtb_size = struct.unpack_from('<I', full_hdr, 1648)[0]
            dtb_addr = struct.unpack_from('<Q', full_hdr, 1652)[0]
            header_size = struct.unpack_from('<I', full_hdr, 1644)[0]
            if dtb_size > 0:
                dtb_pages = (ramdisk_size + page_size - 1) // page_size
                dtb_offset = ramdisk_offset + dtb_pages * page_size
                f.seek(dtb_offset)
                dtb_data = f.read(dtb_size)
                # The X657B section uses an Android DTBO v1 wrapper around an FDT.
                if dtb_data[:4] == b'\xd0\x0d\xfe\xed':
                    pass  # raw FDT
                elif dtb_data[:4] == bytes.fromhex('d7b7ab1e'):
                    import struct
                    magic, total, hdr_sz, ent_sz, count, entries_off, page_sz, version = struct.unpack_from('>8I', dtb_data, 0)
                    if total > len(dtb_data) or hdr_sz < 32 or ent_sz < 32:
                        raise ValueError('Invalid Android DTBO v1 header')
                    for i in range(count):
                        ent = entries_off + i * ent_sz
                        size, offset = struct.unpack_from('>2I', dtb_data, ent)
                        blob = dtb_data[offset:offset + size]
                        assert len(blob) == size and blob[:4] == b'\xd0\x0d\xfe\xed', 'Invalid DTBO FDT entry'
                else:
                    raise ValueError('DTB section is neither raw FDT nor Android DTBO v1')

        return kernel_size, ramdisk_size, page_size, header_version
```

**Common pitfall:** Do NOT use `unpack_from('<Q', ...)` on v0/v1/v2 headers. The kernel_size and ramdisk_size fields are **u32** (4 bytes), not u64. Using 'Q' reads garbage from adjacent fields, causing MemoryError from huge size values.

## Repacking with mkbootimg.py

Location: `/root/android/lineage/system/tools/mkbootimg/mkbootimg.py` (or prebuilt at `out/soong/host/linux-x86/bin/mkbootimg`)

### X657B / MT6761 Specific Parameters

```
--base 0x40000000
--pagesize 2048
--kernel_offset 0x00008000
--ramdisk_offset 0x11b00000
--tags_offset 0x07880000
--dtb_offset 0x07880000          # same as tags_offset on MTK
--board CY-X657B-H6117-D
--cmdline "bootopt=64S3,32S1,32S1 buildvariant=user"
--os_version 11.0.0
--os_patch_level 2022-11
```

**Note:** `dtb_offset` equals `tags_offset` on MediaTek devices (both `0x07880000`). This is intentional — the bootloader places the DTB at the ATAGS address.

### Approach A: Separate DTB (Header v2)

Standard approach — DTB embedded in the boot image header v2 section:

```bash
python3 mkbootimg.py \
  --header_version 2 \
  --pagesize 2048 --base 0x40000000 \
  --kernel_offset 0x00008000 --ramdisk_offset 0x11b00000 \
  --tags_offset 0x07880000 --dtb_offset 0x07880000 \
  --os_version 11.0.0 --os_patch_level 2022-11 \
  --board CY-X657B-H6117-D \
  --cmdline "bootopt=64S3,32S1,32S1 buildvariant=user" \
  --kernel out/arch/arm/boot/zImage \
  --ramdisk /tmp/bu/ramdisk \
  --dtb out/arch/arm/boot/dts/mt6761.dtb \
  -o boot_candidates/boot_A_newdtb.img
```

- Kernel: `CONFIG_ARM_APPENDED_DTB=n` (default)
- Bootloader loads DTB from boot image header, passes to kernel
- Preferred approach for newer bootloaders

### Approach B: Appended DTB (Header v1)

DTB concatenated to end of zImage, kernel self-extracts it:

```bash
# 1. Concatenate
cat out/arch/arm/boot/zImage out/arch/arm/boot/dts/mt6761.dtb > zImage-dtb

# 2. Rebuild kernel with appended DTB support
#    In .config: CONFIG_ARM_APPENDED_DTB=y
#    Run: make olddefconfig then make zImage

# 3. Pack with header v1 (no --dtb flag)
python3 mkbootimg.py \
  --header_version 1 \
  --pagesize 2048 --base 0x40000000 \
  --kernel_offset 0x00008000 --ramdisk_offset 0x11b00000 \
  --tags_offset 0x07880000 \
  --os_version 11.0.0 --os_patch_level 2022-11 \
  --board CY-X657B-H6117-D \
  --cmdline "bootopt=64S3,32S1,32S1 buildvariant=user" \
  --kernel zImage-dtb \
  --ramdisk /tmp/bu/ramdisk \
  -o boot_candidates/boot_B_appended_dtb.img
```

**Why header v1:** Header v2 **requires** a non-empty DTB section. With appended DTB, the DTB is inside the kernel payload, so there's nothing to put in the v2 DTB section. Header v1 has no DTB section — the bootloader passes the entire kernel payload (including appended DTB) to the kernel.

**Kernel requirement:** Must rebuild with `CONFIG_ARM_APPENDED_DTB=y`:
```bash
sed -i 's/# CONFIG_ARM_APPENDED_DTB is not set/CONFIG_ARM_APPENDED_DTB=y/' out/.config
make O=out ARCH=arm ... olddefconfig zImage
```

## Validation

```bash
xxd boot_candidates/boot_A.img | head -1
# Must show: 414e 4452 4f49 4421 = "ANDROID!"
```

## Why This Matters on MediaTek

MediaTek devices store the DTB in a separate partition (`/dev/block/platform/bootdevice/by-name/dtb`), not in the boot image. When building a custom kernel, the new DTB won't match the old one on the dtb partition. Approaches A and B both embed the new DTB in the boot image, bypassing the separate partition entirely.


### X657B-specific v2 header offset correction

The supplied X657B boot dump confirms a one-page 2048-byte header area and `header_size=1660` at offset 1644, `dtb_size=125165` at offset 1648, and `dtb_addr=0x47880000` at offset 1652. Its DTB section starts with an Android DTBO v1 wrapper, not raw FDT magic. Do not use older notes that read `dtb_size` at 1640 or assume the section starts directly with an FDT.
