#!/usr/bin/env python3
"""Build an UNSIGNED X657B Android boot-v2 test candidate. DO NOT FLASH it.

Preserves the supplied boot image's ramdisk and MTK DTB section (including
its 64-byte vendor prefix), replaces only the kernel payload, updates the
legacy Android boot-image SHA-1 ID, and intentionally omits AVB metadata.
"""
import argparse
import gzip
import hashlib
import pathlib
import struct
import sys

PAGE_SIZE_OFF = 36
HEADER_VERSION_OFF = 40
KERNEL_SIZE_OFF = 8
KERNEL_ADDR_OFF = 12
RAMDISK_SIZE_OFF = 16
SECOND_SIZE_OFF = 24
ID_OFF = 576
RECOVERY_DTBO_SIZE_OFF = 1632
HEADER_SIZE_OFF = 1644
DTB_SIZE_OFF = 1648
FDT_MAGIC = b"\xd0\x0d\xfe\xed"
ARM64_MAGIC = b"ARM\x64"
DRAM_BASE = 0x40000000
DEFAULT_KERNEL_ADDR = 0x40080000


def u32(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def put32(data, offset, value):
    struct.pack_into("<I", data, offset, value)


def align(value, alignment):
    return (value + alignment - 1) // alignment * alignment


def parse_boot(path):
    raw = pathlib.Path(path).read_bytes()
    if raw[:8] != b"ANDROID!":
        raise ValueError("input is not an ANDROID! boot image")
    page = u32(raw, PAGE_SIZE_OFF)
    version = u32(raw, HEADER_VERSION_OFF)
    if version != 2:
        raise ValueError(f"expected boot header v2, got v{version}")
    if page < 512 or page & (page - 1):
        raise ValueError("invalid page size")
    if len(raw) < page:
        raise ValueError("truncated header page")

    header = bytearray(raw[:page])
    header_size = u32(header, HEADER_SIZE_OFF)
    if header_size != 1660:
        raise ValueError(f"unexpected v2 header_size={header_size}")

    kernel_size = u32(header, KERNEL_SIZE_OFF)
    ramdisk_size = u32(header, RAMDISK_SIZE_OFF)
    second_size = u32(header, SECOND_SIZE_OFF)
    recovery_size = u32(header, RECOVERY_DTBO_SIZE_OFF)
    dtb_size = u32(header, DTB_SIZE_OFF)
    if second_size or recovery_size:
        raise ValueError(
            "this X657B repacker expects no second or recovery_dtbo section"
        )

    kernel_offset = page
    ramdisk_offset = kernel_offset + align(kernel_size, page)
    second_offset = ramdisk_offset + align(ramdisk_size, page)
    recovery_offset = second_offset + align(second_size, page)
    dtb_offset = recovery_offset + align(recovery_size, page)
    end = dtb_offset + dtb_size
    if end > len(raw):
        raise ValueError("boot image sections exceed file size")

    kernel = raw[kernel_offset:kernel_offset + kernel_size]
    ramdisk = raw[ramdisk_offset:ramdisk_offset + ramdisk_size]
    second = raw[second_offset:second_offset + second_size]
    recovery = raw[recovery_offset:recovery_offset + recovery_size]
    dtb = raw[dtb_offset:dtb_offset + dtb_size]

    # This exact wrapper/FDT layout was measured in the supplied X657B boot.
    if dtb_size < 68 or dtb[64:68] != FDT_MAGIC:
        raise ValueError(
            "expected X657B MTK DTB wrapper with FDT magic at section offset +64"
        )
    return raw, header, page, kernel, ramdisk, second, recovery, dtb, end


def boot_id(parts):
    digest = hashlib.sha1()
    for part in parts:
        digest.update(part)
        digest.update(struct.pack("<I", len(part)))
    return digest.digest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stock-boot", required=True)
    parser.add_argument(
        "--kernel-gz",
        required=True,
        help="gzip-compressed AArch64 Linux Image",
    )
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--kernel-addr",
        type=lambda value: int(value, 0),
        default=DEFAULT_KERNEL_ADDR,
    )
    args = parser.parse_args()

    _, header, page, old_kernel, ramdisk, second, recovery, dtb, _ = parse_boot(
        args.stock_boot
    )
    original_id = boot_id([old_kernel, ramdisk, second, recovery, dtb])
    if header[ID_OFF:ID_OFF + 20] != original_id:
        raise ValueError("stock boot image legacy SHA-1 ID does not match its sections")

    kernel = pathlib.Path(args.kernel_gz).read_bytes()
    if kernel[:2] != b"\x1f\x8b":
        raise ValueError("kernel payload is not gzip")

    image = gzip.decompress(kernel)
    if len(image) < 64 or image[0x38:0x3c] != ARM64_MAGIC:
        raise ValueError("decompressed kernel is not an AArch64 Linux Image")

    text_offset = struct.unpack_from("<Q", image, 8)[0]
    image_size = struct.unpack_from("<Q", image, 16)[0]
    expected_addr = DRAM_BASE + text_offset
    if args.kernel_addr != expected_addr:
        raise ValueError(
            f"kernel_addr {args.kernel_addr:#x} does not match "
            f"DRAM base + Image text_offset ({expected_addr:#x})"
        )

    put32(header, KERNEL_SIZE_OFF, len(kernel))
    put32(header, KERNEL_ADDR_OFF, args.kernel_addr)

    # This section order reproduces the original X657B boot-v2 header ID.
    digest = boot_id([kernel, ramdisk, second, recovery, dtb])
    header[ID_OFF:ID_OFF + 32] = digest + bytes(12)

    output = bytearray(header)
    for section in (kernel, ramdisk, second, recovery):
        output += section
        output += bytes(align(len(output), page) - len(output))
    output += dtb

    output_path = pathlib.Path(args.output)
    output_path.write_bytes(output)

    _, checked_header, _, checked_kernel, checked_ramdisk, _, _, checked_dtb, end = (
        parse_boot(output_path)
    )
    if checked_kernel != kernel:
        raise ValueError("post-write kernel verification failed")
    if checked_ramdisk != ramdisk or checked_dtb != dtb:
        raise ValueError("post-write preserved-section verification failed")
    if checked_header[ID_OFF:ID_OFF + 20] != digest:
        raise ValueError("boot ID verification failed")
    if end != len(output):
        raise ValueError("unexpected trailing data; AVB/footer must not be copied")

    print("UNSIGNED test candidate created — DO NOT FLASH")
    print(f"output={output_path} size={len(output)} bytes")
    print(
        f"kernel_gzip={len(kernel)} bytes; decompressed_Image={len(image)} bytes; "
        f"image_size={image_size}"
    )
    print(f"kernel_addr={args.kernel_addr:#010x}; text_offset={text_offset:#x}")
    print(f"ramdisk={len(ramdisk)} bytes preserved byte-for-byte")
    print(
        f"MTK_DTB_section={len(dtb)} bytes preserved byte-for-byte; FDT offset=64"
    )
    print(f"boot_header=v2 page_size={page}; boot_id_sha1={digest.hex()}")
    print(f"sha256={hashlib.sha256(output).hexdigest()}")
    print(
        "AVB footer/vbmeta intentionally omitted; bootloader unlock/verification "
        "state is not assumed."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
