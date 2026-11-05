# X657B LK handoff audit — 2026-11-05

## Verified on recovered handset binaries

- `x657b-lk.img` and `x657b-lk2.img` are each 1 MiB and differ in only 96 warning-string bytes; executable code is identical.
- LK Thumb parser at `0x44b28` finds `bootopt=`, checks the selector at offset `0x12`, and sets the 64-bit-kernel state for `64`.
- Caller at `0x4430e` passes the Android boot header cmdline field (`header + 0x40`) into that parser. The candidate's `bootopt=64S3,32S1,64S1` therefore reaches the parser.
- The 64-bit path calls `lk_jump64` at `0x24440`; its SMC wrapper at `0x30098` issues SMC function ID `0x82000115` (`MTK_SIP_KERNEL_BOOT`).
- The 64-bit call arguments are `(entry, tags, 0, 1)`, yielding SMC registers `r1=entry`, `r2=DTB`, `r3=0`, `r4=1`. The secure firmware performs the execution-state transition.
- The gzip path calls the inflate helper at `0x26c4c`.

## Candidate image

File: `x657b-arm64-boot-unsigned-test.img`

SHA-256: `a18ec200bdaed5603a0052f1f1cdc3fa3e268b52a62c490bdaa7f61cc2004f12`

- Android boot header v2, 2048-byte pages, 32 MiB partition-sized image.
- AArch64 Image.gz: 12,587,773 bytes; decompressed Image: 37,337,104 bytes.
- Image header: `text_offset=0x80000`, `image_size=0x02822000`.
- Kernel entry/load address `0x40080000`; DTB/tags `0x47880000`; ramdisk `0x51b00000`.
- Candidate DTB table: total size 125,165; one entry at offset 64; embedded FDT totalsize 125,101; valid `0xd00dfeed` magic.
- DTB is byte-identical to the saved live/original image's DTB. FDT identifies MT6761, four Cortex-A53 CPUs, PSCI SMC, and a GICv3 interrupt controller.
- Candidate preserves the original ramdisk. Its init and Magisk executables are ELF32 ARM, consistent with `CONFIG_COMPAT=y` and the 32-bit userspace target.

## Do not conflate images

Saved `boot-x657b-live.img` SHA-256 is `122e9ede780cdcaad26df4e6b43749f06de9c699ec2217ff27b98317e1571657`, matching the recorded `boot-x657b-original.img` backup. Its kernel is a 32-bit ARM zImage, kernel address `0x40008000`, and bootopt selector `32S1`. It is not the ARM64 candidate. The earlier ARM64 candidate hash `162b0d88c1f91718ad359241599cc38ec6d1047c1fa811c073d00f138c83c710` is also distinct from the current candidate.

## Remaining blockers

- No verified successful boot of the current ARM64 candidate.
- Exact AVB acceptance of the unsigned candidate is unresolved; do not flash speculatively.
- Installed DTBO hash does not match the active vbmeta descriptor; its functional overlay has not yet been inspected.
- Kernel and module artifacts previously came from separate builds with different recorded Image hashes. A CI branch is packaging Image, Image.gz, config, both Module.symvers files, and modules from one run.
- No flash/test is authorized until a reversible recovery path is established.

Reference MT6761 LK sources: [SMC ID table](https://github.com/svoboda18/lk/blob/37ec8bcbc4361c0e267617f517d154656804c17a/platform/mt6761/include/platform/plat_smc_id_table.h), [memory layout](https://github.com/svoboda18/lk/blob/37ec8bcbc4361c0e267617f517d154656804c17a/platform/mt6761/include/platform/memory_layout.h), [platform rules](https://github.com/svoboda18/lk/blob/37ec8bcbc4361c0e267617f517d154656804c17a/platform/mt6761/rules.mk).


## AVB behavior found in the matching MT6761 LK source

The MT6761 `platform/common/boot/avb20/load_vfy_boot.c` path calls `avb_slot_verify()`. Its linked libavb code checks the top-level vbmeta `VERIFICATION_DISABLED` flag; when set, it loads requested partitions without processing hash, hashtree, or chained-vbmeta descriptors. The handset's saved top-level vbmeta flags are `3`, including `VERIFICATION_DISABLED`.

This makes the candidate's unsigned embedded vbmeta and the DTBO descriptor mismatch **unlikely** to be boot blockers under the matching LK/libavb behavior. The secure policy's `img_auth_required` value and the exact runtime path have not been instrumented on the handset, so this is not a boot-test result.

AOSP reference: [libavb slot verification](https://android.googlesource.com/platform/external/avb/+/android17-release/libavb/avb_slot_verify.h).


## DTBO partition structure

The 3,707 bytes after the Android DT table are not random padding: the captured tail begins with MediaTek image-header magic `88 16 88 58`, the ASCII `cert1` marker, and MTK extended-header magic `89 16 89 58`. The DT table size (170,645) plus this tail (3,707) equals the vbmeta descriptor image size (174,352).

The matching MT6761 LK source's `load_dtbo_buffer()` validates the table, consults the `dtbo` secure-image policy, optionally verifies the MTK cert chain via `sec_img_auth_init()` / `sec_img_auth()`, then selects the overlay by ODM index. This MTK image-auth path is separate from AVB hash-descriptor processing. The current device boots using this same installed DTBO, but the actual overlay's panel/touch content still needs inspection.

References: [MTK cert1/cert2 format](https://github.com/AgentFabulous/basic_img_signer), [MTK LK certificate-container analysis](https://github.com/DexopT/LK-Bootloader-Security-Research/blob/master/docs/05-stage2-lk-bootloader.md).


## Device-specific PMIC module correction

The candidate base FDT's main PMIC is `mediatek,mt6357`; its accdet node is `mediatek,mt6357-accdet`, and its gauge/charger/LED nodes are MT6357. The generated config correctly enables MT6357 battery and accdet support but also builds `mt6359_battery.ko` and `mt6359-accdet.ko`. The MT6359 gauge/accdet drivers match MT6359 compatibles, absent from this FDT. The previous module build emitted duplicate `accdet_late_init` exports from MT6357 and MT6359 accdet modules. The next config revision will disable `CONFIG_BATTERY_MT6359` and `CONFIG_SND_SOC_MT6359_ACCDET`, retain MT6357, and package all in-tree modules as well as the six external connectivity modules.


### MTK secure-policy caveat

The MT6761 `get_vfy_policy()` result is selected from MediaTek secure-policy bits associated with SBC/lock state. The reference policy headers include both verification-enabled and verification-disabled states. Android `ro.boot.*` properties and AVB flags alone do not establish the DTBO `img_auth_required` value; the handset's `seccfg`/secure-policy state has not been read. The currently running system's use of this DTBO suggests MTK auth succeeds or is not required, but the appended certificate chain has not been independently verified.
