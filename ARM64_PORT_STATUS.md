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

## Important unresolved hardware detail
- The X657B ARM32 defconfig specifies a 720x1600 LCM configuration.
- The selected LCM C driver currently defines `FRAME_WIDTH=720` and `FRAME_HEIGHT=1520`.
- This 80-pixel height discrepancy must be reconciled against the actual panel/stock DT and display behavior before any boot attempt. Do not silently assume either value is correct.

## Boot-chain / DT findings
- The supplied LK-embedded DTB is a valid version-17 DTB and contains MT6761-compatible nodes.
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
- CI is still the authority for whether the source actually compiles. A successful defconfig/olddefconfig is not a successful kernel build.
- Next gates: successful compile, output ELF/Image verification, boot-image/LK handoff review, then a controlled non-flashing compatibility review. Device boot testing requires separate explicit approval.
