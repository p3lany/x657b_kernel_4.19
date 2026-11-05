# X657B ARM64 test-boot failure analysis

**Status:** Investigation in progress. The experimental ARM64 boot froze at the Infinix logo; the original boot was restored. No new image is approved for flashing.

## Evidence already recorded

The prior structural-validation report for `x657b-arm64-boot-unsigned-test.img` records:

- 32 MiB boot image; Android boot header v2; page size 2048.
- Gzip kernel payload: 12,587,773 bytes.
- Decompressed AArch64 Image: 37,337,104 bytes.
- Kernel load address: `0x40080000`.
- Original ramdisk preserved byte-for-byte (942,301 bytes).
- DTB/DTBO wrapper preserved byte-for-byte (125,165 bytes).
- Command line: `bootopt=64S3,32S1,64S1 buildvariant=user`.
- AVB footer structure verified, but algorithm NONE / unsigned.
- The report explicitly did not verify the actual X657B LK's 64-bit path or the bootloader's acceptance of the unsigned image.

The X657B TWRP device tree independently records the stock configuration as ARM32 userspace with 64-bit binder and stock command line `bootopt=64S3,32S1,32S1`.

## High-priority hypothesis: LK 64-bit decompression output limit

Public MediaTek LK source contains this flow:

1. Parse `bootopt=`; inspect the third field at offset `0x12`.
2. If it starts with `64`, set `g_is_64bit_kernel`.
3. For the 64-bit path, decompress the kernel into the address from the boot header.
4. In one MTK LK implementation, the default output limit is `0x1C00000` (28 MiB), with an optional `KERNEL_DECOMPRESS_SIZE` build-time override.

The recorded experimental kernel expands to 37,337,104 bytes (about 35.6 MiB), which exceeds 28 MiB by 7,976,976 bytes (about 7.61 MiB).

If the X657B LK uses this same default and has no larger override, the experimental image may fail inside LK's decompression stage before Linux starts. A frozen boot logo is consistent with that, but does not prove it.

Important qualification: other MTK LK trees use a required or larger `KERNEL_DECOMPRESS_SIZE` override (for example, 50 MiB). Therefore the generic 28 MiB value must NOT be assumed to be the X657B value.

## Second high-priority check: actual LK bootopt parser and jump path

The generic MTK implementation reads the third bootopt field. Thus the candidate's `64S1` requests the 64-bit-kernel path, whereas the stock X657B command line ends in `32S1`. The exact X657B LK binary must be checked for:
- Whether it implements the same parser.
- Whether the 64-bit path uses `jumparch64_smc` / secure-monitor handoff.
- The effective decompression output limit and scratch/load memory layout.
- Whether it accepts the image's AVB state.

## Do not repeat these mistakes

- Do not rebuild and flash the same 37.3 MB decompressed kernel until the LK output limit is known.
- Do not assume the generic LK source is byte-for-byte or config-identical to X657B's 1 MiB LK.
- Do not modify LK/LK2, preloader, TEE, or vbmeta as an experiment.
- Do not flash another unsigned candidate without confirming unlock/AVB behavior and a recovery path.

## Required next evidence

Analyze the actual X657B `lk.img` dump (previously read from the device) to determine the compiled 64-bit decompression path and its limit. If source is unavailable, inspect the binary's strings, literal pools, references to the decompressor and SMC jump routine, and relevant code paths. Compare against `lk2.img` only if the normal boot path is shown to select it.

Then inspect the exact failed image bytes and SHA-256 to verify that the file analyzed is the file actually flashed.

## Sources

- X657B device tree / stock BoardConfig: https://github.com/twrpdtgen/android_device_infinix_Infinix-X657B/blob/full_x657b_h6117-user-10-QP1A.190711.020-136739-release-keys/BoardConfig.mk
- MediaTek LK bootopt parser and 64-bit kernel decompression path (reference implementation): https://github.com/dguidipc/gemini-lk/blob/master/lk/app/mt_boot/mt_boot.c
- Another MTK LK implementation showing `KERNEL_DECOMPRESS_SIZE` handling: https://github.com/svoboda18/lk/blob/main/app/mt_boot/mt_boot.c
- MT6739 example setting a 50 MiB decompression limit: https://huaweicloud.csdn.net/6510fe3f993dd34278ee5730.html

This document records a hypothesis and the evidence required to confirm or reject it. It is not a claim that the root cause has been proven.
