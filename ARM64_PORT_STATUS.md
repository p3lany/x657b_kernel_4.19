# X657B ARM64 Port — Engineering Status

## Target
- Device: Infinix Smart 5 X657B
- SoC: MediaTek MT6761 family; Cortex-A53 cores support AArch64
- Source tree: Linux 4.19.325 device kernel
- Goal: build and validate an AArch64 kernel first; Android userspace/GSI compatibility is a separate milestone.

## Confirmed source-tree support
- `arch/arm64/Kconfig.platforms` defines `MACH_MT6761`.
- The MT6761 ARM64 platform option selects `ARMV7_COMPAT` and `ARMV7_COMPAT_CPUINFO`, so the source has an AArch32 compatibility path for 32-bit userspace.
- The experimental X657B config keeps `CONFIG_COMPAT=y` and `CONFIG_NR_CPUS=4`.
- The original X657B ARM32 defconfig independently confirms `CONFIG_TOUCHSCREEN_MTK_NT36572_COMMON=y`; the matching NT36572 driver exists at `drivers/input/touchscreen/nt36572_common/`. The ARM64 port now sources that driver's Kconfig correctly and CI explicitly checks that the option survives `olddefconfig`.
- The only matching X657B LCM driver directory in this source tree is `nt36525b_hdp_dsi_vdo_txd_mdt_x657b`; the defconfig selects that driver only.

## Panel resolution alignment
- The X657B ARM32 defconfig specifies a 720x1600 LCM configuration.
- The selected X657B LCM C driver initially declared `FRAME_HEIGHT=1520`, inconsistent with the stock X657B config.
- The driver was updated to `FRAME_WIDTH=720` and `FRAME_HEIGHT=1600` to match the stock device configuration. This is a source/config consistency correction, not proof of panel operation; final validation still requires matching the live stock panel parameters and a controlled display test.

## Boot-chain / DT findings
- The supplied LK-embedded DTB is a valid version-17 DTB. Its root identifies MT6761 and it describes four Cortex-A53 CPUs with PSCI enable-method. Its initial memory node declares 512 MiB at `0x40000000`, but this is not necessarily the final RAM map: the matching MTK LK source has an mblock routine that rewrites the memory node from detected DRAM/reserved-memory ranges before handoff.
- The source tree also contains `arch/arm64/boot/dts/mediatek/mt6761.dts`; its CPU topology and base memory address match the core LK-DTB facts. This is encouraging evidence that the SoC's DT description is usable in an AArch64 kernel, not proof that every board node matches.
- Important discrepancy: the LK-embedded DTB's generic `touch` node uses `mediatek,touch`, while the kernel MT6761 DTS uses `goodix,touch`. The embedded LK DTB therefore must not be treated as a drop-in replacement without checking the actual kernel handoff DTB and touchscreen bindings.
- A DTB is not intrinsically ARM32 or ARM64; reuse with an AArch64 kernel depends on matching node bindings, addresses, interrupts, clocks, reserved memory, and driver expectations.
- LK/TEE firmware strings contain references to 64-bit kernel handoff paths, but strings alone do not prove the active handoff path or establish SMC IDs. Those require code-level verification.
- No kernel has been flashed and no device partitions have been modified.

## Android userspace limitation
- Prior vendor audit found only a small set of 64-bit fingerprint-related vendor libraries; most observed GPU, camera, audio, and MediaTek HAL components are 32-bit.
- A 64-bit kernel with the existing 32-bit Android userspace is the nearer-term target. A fully 64-bit Android userspace/GSI would require compatible 64-bit vendor components, especially graphics and core HALs.

## Build status
- GitHub Actions workflow: `.github/workflows/x657b-arm64.yml`
- It validates the defconfig, builds `Image`, and checks the AArch64 Linux Image magic at byte offset `0x38`.
- The build workflow uses an explicit Clang AArch64 target and AArch64 GNU binutils; this avoids accidentally invoking a host x86-64 compiler target.
- First successful CI ARM64 build: run #5, source commit `fac5942b27f6c9cbfd0134d9ee7d8843614ca7ab`. The uploaded `Image` is 35,561,488 bytes; `file` identifies it as a Linux kernel ARM64 boot executable Image (little-endian, 4K pages), and the `ARM\x64` magic is present at byte offset `0x38`. SHA-256: `8819dc86597892c48a9a681ed4ce8ff984b467510cce711bb96b18ef1a9588fb`.
- Build #5 logs show the NT36xxx touchscreen objects and selected X657B LCM object were compiled. A later build is checking the cleaned-up Kconfig wiring and explicitly verifies `CONFIG_TOUCHSCREEN_MTK_NT36572_COMMON=y` survives `olddefconfig`.
- Stock boot image inspection: Android boot header version 2, 2048-byte page size, 32 MiB image, 10,548,720-byte ARM32 zImage, 942,301-byte gzip ramdisk, and a 125,165-byte DTB section. The DTB begins after a 64-byte pad and matches the supplied LK-embedded DTB byte-for-byte. The image also contains an AVB 1.0 footer and a signed SHA256_RSA2048 vbmeta block.
- The raw ARM64 Image (35,561,488 bytes) is larger than the 32 MiB stock boot image. A gzip-compressed copy is 12,485,352 bytes, and LK contains explicit gzip-decompression and 64-bit-kernel handoff strings. This makes compressed-kernel boot-image integration plausible, but the exact LK decompression destination and AArch64 load address still need validation.
- Boot-image DTB nuance: the v2 DTB section begins at the page-aligned section offset with 64 zero bytes before the actual FDT magic; the header's `dtb_size` includes those 64 bytes. The FDT itself is 125,101 bytes. The stock image's DTB region must be preserved as a whole, and a generic mkbootimg repack must not silently drop that prefix. The exact X657B LK parser's handling of this prefix remains to be confirmed.
- The original boot image can be reconstructed byte-for-byte from its header, kernel, ramdisk, DTB section, AVB block and footer. This validates the section parser. Any modified kernel invalidates the original signed AVB hash/signature; do not flash a repacked image until the AVB strategy and bootloader state are verified.
- A public MT6761 LK source has a memory map that matches the stock boot image's 32-bit kernel (`0x40008000`), DTB (`0x47880000`) and ramdisk (`0x51B00000`) addresses exactly. That map defines the AArch64 kernel base as `0x40080000`, with a maximum kernel/decompression region of `0x07800000` (120 MiB); the [MT6761 platform rules](https://github.com/svoboda18/lk/blob/main/platform/mt6761/rules.mk) set the same `KERNEL_DECOMPRESS_SIZE`, and [LK's memory layout](https://github.com/svoboda18/lk/blob/main/platform/mt6761/include/platform/memory_layout.h) confirms the address limits. The successful ARM64 Image declares an image footprint of 39,292,928 bytes, within that reference limit. The X657B LK binary itself contains gzip-decompression and 64-bit handoff strings. This is strong cross-checking evidence, but the public LK source is a reference build, not a byte-for-byte source match for the phone's LK binary.
- The boot-image repack plan therefore uses a gzip-compressed ARM64 Image and `kernel_addr=0x40080000`, while retaining the original ramdisk and DTB addresses. This layout has not yet been boot-tested.
- Next gates: complete the latest clean build, inspect its generated config and image, prepare a clearly marked non-flashing boot candidate, then validate LK/AVB compatibility. Device boot testing requires separate explicit approval.
