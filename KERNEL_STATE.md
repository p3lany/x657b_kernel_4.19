# X657B ARM64 KERNEL — CURRENT PROJECT STATE

**Updated:** 2026-11-05
**Active branch:** `arm64/x657b-defconfig`
**Target:** Infinix Smart 5 X657B / MT6761
**First milestone:** AArch64 kernel with `CONFIG_COMPAT=y`, booting the existing 32-bit Android userspace.
**Safety rule:** No partition writes or flashing without a separate explicit user instruction.

## Confirmed progress

- ARM64 defconfig exists at `arch/arm64/configs/x657b_arm64_defconfig`.
- Required architecture options include `CONFIG_ARM64=y`, `CONFIG_MACH_MT6761=y`, `CONFIG_COMPAT=y`, `CONFIG_NR_CPUS=4`, Android Binder, and Ashmem.
- GitHub Actions run **#17** (run ID `41919324334`, source commit `cc3db5e121c174a80df3fb68d32cb8e64badd777`) completed successfully.
- Run #17 produced an ARM64 `Image` of 35,561,488 bytes. Header checks passed: magic `ARM\\x64` at offset `0x38`, text offset `0x80000`, image_size `39,292,928`.
- The prior artifact did **not** contain `Image.gz`, despite the earlier workflow intending to build it. This is why the workflow now builds the compressed target explicitly and fails unless both images exist and decompress identically.
- Source commit `78352aa11f2e66b258b67848b63a75503e47dfa3` added `mediatek,touch` to the MediaTek TPD framework's OF match table.
- Workflow commits `8088d1aa3afc132cbe4d65c6706b64cde467cdf5` and `f4286c1a2bc8b463822eba4555ab234d1da4c59c` make the compressed-image build explicit and retain verification/config diagnostics. The workflow watches its own path, so pushes to this branch should trigger a fresh run. The latest run's completion has not yet been independently confirmed.

## Boot-image sizing and safety

- The supplied live boot image is a 32 MiB partition-sized dump, Android boot header v2, with a 125,101-byte embedded FDT and an AVB footer.
- Its original kernel is about 10.5 MiB. The previous ARM64 Image is about 35.6 MiB uncompressed and cannot be inserted as-is into this boot partition.
- Compressing that previous Image locally with gzip -9 produced 12,485,128 bytes; this is an estimate for sizing, **not** the new workflow artifact. A compressed ARM64 kernel plus the existing ramdisk and DTB should fit within 32 MiB.
- Replacing the kernel changes the AVB-authenticated image. Bootloader lock/verified-boot state is not yet confirmed.
- The LK binary contains strings indicating 64-bit kernel handoff and gzip decompression, but this alone does not prove that a repacked ARM64 boot image will be accepted.
- The original boot header's kernel address is 32-bit-era `0x40008000`. The correct ARM64 load address and LK memory placement still require validation before packaging.

## Hardware/source issues still open

1. **Touchscreen binding:** the extracted X657B DTB exposes a root-level `mediatek,touch` node. It does not contain `mediatek,cap_touch`. The Novatek NT36xxx I2C driver currently matches `mediatek,cap_touch`; adding `mediatek,touch` to the generic TPD framework fixes only the framework match, not proof that the I2C controller driver probes. Do not claim touch is solved until the real controller binding is established.
2. **Kernel baseline:** this source tree identifies itself as Linux `4.19.325`, while the user's reported running kernel is `4.19.127-gaff2307ea494-dirty`. The difference may affect vendor kernel modules and ABI compatibility; inspect module requirements before boot testing.
3. **Device-tree and peripherals:** display, storage, USB, Wi-Fi, audio, sensors, camera, charger, and modem paths need a board-specific compatibility audit and eventually on-device testing.
4. **Boot path:** temporary boot support, AVB behavior, kernel load address, and a safe recovery path remain unverified.
5. **Full ARM64 Android:** separate from the first milestone. The available vendor audit shows only a small set of 64-bit fingerprint libraries; core graphics/camera/audio/MediaTek vendor components appear predominantly 32-bit. Do not assume a true 64-bit Android userspace or 64-bit app support is possible without compatible 64-bit vendor HALs/blobs.

## Next actions

1. Confirm the fresh CI run after the workflow changes.
2. Verify the new `Image.gz` decompresses byte-for-byte to `Image`; retain the resolved config and verification log.
3. Resolve the actual touchscreen controller binding from the complete runtime DTB / stock driver evidence; do not add speculative OF aliases.
4. Validate ARM64 boot-header address and LK loading/decompression behavior against the actual X657B LK.
5. Build a non-flashed candidate boot image only after the above checks, preserve the original image, and verify size/header/DTB/ramdisk/footer handling.
6. Ask the user for a read-only bootloader-state check only when needed. Never flash without explicit consent.

## Current status

**Kernel compilation:** previously successful for an earlier commit.
**Latest ARM64 source revision:** touchscreen framework change committed.
**Fresh compressed build:** requested by CI workflow changes; not yet confirmed.
**Bootable ARM64 image:** not yet established.
**Device test:** not performed for this ARM64 build.
**Partition changes:** none.


## Additional X657B boot-layout reference (2026-11-05)

A public TWRP device tree for the X657B (Android 10-era branch) reports:
- Android userspace target is 32-bit ARMv7-A / armeabi-v7a + armeabi, with `TARGET_USES_64_BIT_BINDER := true`.
- MT6761 board platform.
- Boot header v2, base `0x40000000`, page size 2048.
- Kernel command line begins `bootopt=64S3,32S1,32S1`.
- Ramdisk offset `0x11b00000`, tags offset `0x07880000`.
- Boot and recovery partition sizes are each `40,894,464` bytes (about 39 MiB).
- The BoardConfig supports an embedded DTB path and an alternate prebuilt-kernel + separate-DTB path; it also references a separate DTBO image.

These are useful board-specific reference values, not proof they match every firmware revision or the user's current partition map. In particular, do not blindly copy these addresses into a repacked image. Compare against the user's actual boot image header, embedded DTB, current LK behavior, and current partition size first.

Reference: https://github.com/twrpdtgen/android_device_infinix_Infinix-X657B/blob/full_x657b_h6117-user-10-QP1A.190711.020-136739-release-keys/BoardConfig.mk
