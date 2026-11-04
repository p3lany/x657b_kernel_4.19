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
- The X657B NT36572 touchscreen driver exists at `drivers/input/touchscreen/nt36572_common/`; the defconfig enables `CONFIG_TOUCHSCREEN_MTK_NT36572_COMMON=y`.
- The only matching X657B LCM driver directory in this source tree is `nt36525b_hdp_dsi_vdo_txd_mdt_x657b`; the defconfig selects that driver only.

## Panel resolution alignment
- The X657B ARM32 defconfig specifies a 720x1600 LCM configuration.
- The selected X657B LCM C driver initially declared `FRAME_HEIGHT=1520`, inconsistent with the stock X657B config.
- The driver was updated to `FRAME_WIDTH=720` and `FRAME_HEIGHT=1600` to match the stock device configuration. This is a source/config consistency correction, not proof of panel operation; final validation still requires matching the live stock panel parameters and a controlled display test.

## Boot-chain / DT findings
- The supplied LK-embedded DTB is a valid version-17 DTB with root compatible `mediatek,MT6761`, four `arm,cortex-a53` CPU nodes, `arm,psci-1.0` using SMC, and an `arm,gic-v3` interrupt controller.
- A DTB is not intrinsically ARM32 or ARM64. Its CPU nodes and PSCI/GIC description are architecture-neutral; reuse still depends on matching node bindings, addresses, interrupts, clocks, reserved memory, and driver expectations.
- LK/TEE firmware strings contain references to gzip decompression and 64-bit kernel handoff paths. These are encouraging static indicators, not proof that the active boot path accepts this exact ARM64 payload. No SMC ID is assumed.
- A public X657B TWRP device tree records boot header v2, base `0x40000000`, boot page size 2048, ramdisk offset `0x11b00000`, tags offset `0x07880000`, DTB in boot image, separate DTBO, and a 40,894,464-byte boot partition. See [X657B BoardConfig.mk](https://github.com/twrpdtgen/android_device_infinix_Infinix-X657B/blob/full_x657b_h6117-user-10-QP1A.190711.020-136739-release-keys/BoardConfig.mk). Treat these as reference values; the actual stock boot header must be inspected before packaging.
- The first compiled ARM64 Image has `text_offset=0x80000`; do not infer or hardcode the final kernel load address until the original boot image and LK behavior are checked.
- No kernel has been flashed and no device partitions have been modified.

## X657B driver coverage audit
- The stock board config was overlaid onto the ARM64 config, then filtered against this source tree. The ARM64 candidate now selects only the available camera driver directories `s5k3l6_mipi_raw`, `gc8034_mipi_raw`, and `ov8856_mipi_raw`; several stock-listed project-specific variants and GC6153/GC6133 drivers are absent from this checkout.
- The MT6370 flashlight driver and MT6357 LED driver are present. The DTB also contains `mediatek,flashlights_ocp81373`, but this checkout has no OCP81373 driver or Kconfig symbol. Do not treat MT6370 as a substitute for OCP81373.
- `drivers/input/fingerprint/Kconfig` exposes the fingerprint selection option, but this checkout has no GF318M driver implementation. The config flag alone does not provide working fingerprint support.
- These are hardware-functionality gaps, not blockers to compiling or initially booting the ARM64 kernel. They must be addressed before claiming full device feature parity.

## Android userspace limitation
- Prior vendor audit found only a small set of 64-bit fingerprint-related vendor libraries; most observed GPU, camera, audio, and MediaTek HAL components are 32-bit.
- A 64-bit kernel with the existing 32-bit Android userspace is the nearer-term target. A fully 64-bit Android userspace/GSI would require compatible 64-bit vendor components, especially graphics and core HALs.

## Build status
- GitHub Actions workflow: `.github/workflows/x657b-arm64.yml`
- **First ARM64 kernel compile succeeded:** run #5, source commit `fac5942b27f6c9cbfd0134d9ee7d8843614ca7ab`.
- That build produced a 35,561,488-byte AArch64 `Image` with SHA-256 `8819dc86597892c48a9a681ed4ce8ff984b467510cce711bb96b18ef1a9588fb`; the ARM64 magic `ARM\\x64` was verified at offset `0x38`. Header reports `text_offset=0x80000` and `image_size=39292928`.
- A local gzip payload was produced at 12,485,358 bytes and decompressed byte-for-byte to the same `Image`. The current CI candidate also generates and verifies `Image.gz` before uploading it.
- Run #5 used an earlier config. The separate `arm64/x657b-board-overlay` branch merges X657B board options, drops undefined symbols, and selects only camera drivers present in this checkout. Its latest build is run #15; config generation and hardware-option validation passed, kernel compilation is in progress.
- The build workflow uses an explicit Clang AArch64 target and AArch64 GNU binutils; this avoids accidentally invoking a host x86-64 compiler target.
- A successful compile proves an AArch64 kernel image can be produced, not that it boots on the phone. Next gates: complete the board-overlay build, inspect the generated config and image, package against the actual stock boot header/ramdisk/DTB, and review LK handoff. Device boot testing requires separate explicit approval.
