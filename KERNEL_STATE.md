# X657B ARM64 KERNEL — CURRENT PROJECT STATE

**Updated:** 2026-11-05  
**Current integration candidate:** `arm64/x657b-board-overlay-v2`  
**Base branch:** `arm64/x657b-defconfig`  
**Target:** Infinix Smart 5 X657B / MT6761  
**First milestone:** AArch64 kernel with `CONFIG_COMPAT=y`, booting the existing 32-bit Android userspace.

## Safety rule

No partition writes, flashing, or boot-image installation without a separate explicit user instruction. All work below is repository/CI/read-only analysis.

## Current CI state

- Kernel workflow run **#29** (`41926058830`) is building the board-overlay candidate. Configuration generation passed; full ARM64 kernel compilation is in progress.
- Connectivity workflow run **#4** (`41926058869`) has checked out all donor sources and generated the ARM64 config successfully. The kernel/in-tree-module build is in progress; external WMT/Wi-Fi/BT/GPS/FM modules have not yet been built or ABI-verified.
- Earlier board-overlay run #21 failed during the TEEI v300 build because `drivers/tee/teei/300/tee/tee_core.c` could not find `capi_proxy.h`. Later commits restore that header and additional missing TEEI v300 sources; run #29 is the validation of the repaired tree.
- Do not call the latest kernel or connectivity builds successful until the run conclusion and artifacts confirm it.

## Architecture and board support

- The ARM64 defconfig preserves `CONFIG_ARM64=y`, `CONFIG_COMPAT=y`, MT6761 platform support, Android Binder/BinderFS/Ashmem, and X657B-specific options.
- The X657B base DTB exposes `mediatek,touch`; the Android 11 reference DTBO adds `cap_touch@62` with `mediatek,cap_touch`. These are separate bindings for the MediaTek TPD framework and Novatek I2C controller. The user's currently installed DTBO still needs confirmation.
- The board candidate restores Microtrust TEEI v300 source to match the stock configuration/firmware evidence. Build success does not prove runtime TEE/SMC compatibility.
- The stock vendor-module audit found 11 shipped modules are ELF32 ARM with 4.19.127 vendor vermagic. They cannot be loaded by the AArch64 kernel. The connectivity workflow is attempting compatible ARM64 builds for WMT, Wi-Fi, Bluetooth, GPS, and FM.
- Known gaps include the missing OCP81373 flashlight driver, missing standalone tran_fp/GF318M sensor driver, incomplete camera sensor coverage, and stock Transsion hooks absent from the source config. Do not claim full stock peripheral parity.

## Stock boot image facts verified from the supplied 32 MiB dump

- File size: 33,554,432 bytes; SHA-256: `122e9ede780cdcaad26df4e6b43749f06de9c699ec2217ff27b98317e1571657`.
- Android boot header v2, 2048-byte page size.
- Original kernel: 10,548,720 bytes at address `0x40008000`.
- Ramdisk: 942,301 bytes at address `0x51b00000`.
- Header v2 fields: `recovery_dtbo_size` offset 1632; `recovery_dtbo_offset` offset 1636; `header_size=1660` offset 1644; `dtb_size=125165` offset 1648; `dtb_addr=0x47880000` offset 1652.
- The DTB section begins with an Android DTBO v1 wrapper (magic `0xd7b7ab1e`) containing an FDT entry at offset 64. Preserve the entire section, not just the FDT payload.
- The image contains AVB authentication. Replacing the kernel invalidates the original authenticated digest/signature. Bootloader lock/verified-boot state remains unknown.
- The reference MT6761 LK map suggests AArch64 kernel load address `0x40080000` and a 120 MiB decompression region, but the exact phone LK handoff still requires validation.

## Important: legacy boot candidates are not the current ARM64 build

The files under `boot_candidates/boot_*.img` and the D1/D2 test notes in `KERNEL_TESTLOG.md` are historical June 2026 experiments. They predate the current ARM64 board-overlay/TEEI work and are **not approved or verified ARM64 boot images**. Do not flash or use them as the output of the current ARM64 project.

The previous D1r experiment hit an LK `cmdline overflow`; D1s passed LK but the kernel crashed early. Later D2 candidates were proposals for that older experiment, not evidence that the current ARM64 kernel boots.

## Next gates

1. Complete run #29 and inspect the generated ARM64 Image, gzip payload, config, and driver-object verification.
2. Complete connectivity run #4 and verify each external module is ELF64/AArch64 with vermagic matching the exact kernel release.
3. Obtain the exact currently installed DTBO and resolve the display/panel-name conflict before claiming touchscreen/display compatibility.
4. Verify the actual phone's bootloader/AVB state and boot partition size using read-only queries.
5. Only then create a **non-flashed** ARM64 boot candidate, preserving the exact stock ramdisk, full wrapped DTB section, header metadata, and AVB implications.
6. A controlled device boot test remains a separate milestone and requires explicit user approval before any write.

## Current status

**ARM64 config generation:** passed in run #29.  
**Full ARM64 kernel compile:** in progress.  
**ARM64 connectivity modules:** kernel/in-tree build in progress; external modules pending.  
**Correct X657B boot-header parsing:** verified and documented.  
**Non-flashed ARM64 boot image:** not built.  
**Successful ARM64 device boot:** not demonstrated.  
**Partition changes:** none.
