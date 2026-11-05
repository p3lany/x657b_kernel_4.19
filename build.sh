#!/usr/bin/env bash
# Reproducible X657B ARM64 kernel build.
# This replaces the legacy ARCH=arm/zImage script.
# External MT6761 connectivity modules are built by:
# .github/workflows/build-x657b-arm64-connectivity.yml

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${OUT:-$ROOT/out-arm64}"
JOBS="${JOBS:-$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 2)}"
DEFCONFIG="${DEFCONFIG:-x657b_arm64_defconfig}"
CROSS_COMPILE="${CROSS_COMPILE:-aarch64-linux-gnu-}"
CROSS_COMPILE_ARM32="${CROSS_COMPILE_ARM32:-arm-linux-gnueabi-}"
CC="${CC:-clang-11}"

if [ "${CLEAN:-0}" = "1" ]; then
    rm -rf "$OUT"
fi
mkdir -p "$OUT"

if ! command -v "${CC%% *}" >/dev/null 2>&1; then
    echo "ERROR: compiler '$CC' not found." >&2
    echo "Use CI or install the Clang toolchain used by the project workflow." >&2
    exit 1
fi
if ! command -v "${CROSS_COMPILE}ld" >/dev/null 2>&1; then
    echo "ERROR: AArch64 linker '${CROSS_COMPILE}ld' not found." >&2
    echo "Set CROSS_COMPILE to your AArch64 cross-toolchain prefix." >&2
    exit 1
fi
if ! command -v "${CROSS_COMPILE_ARM32}gcc" >/dev/null 2>&1; then
    echo "ERROR: ARM32 compat toolchain '${CROSS_COMPILE_ARM32}gcc' not found." >&2
    echo "CONFIG_COMPAT requires the 32-bit compat/vDSO toolchain in this build." >&2
    exit 1
fi

MAKE_ARGS=(
    O="$OUT"
    ARCH=arm64
    "CC=$CC --target=aarch64-linux-gnu"
    "CROSS_COMPILE=$CROSS_COMPILE"
    "CROSS_COMPILE_ARM32=$CROSS_COMPILE_ARM32"
    "LD=${CROSS_COMPILE}ld"
    "AR=${CROSS_COMPILE}ar"
    "NM=${CROSS_COMPILE}nm"
    "OBJCOPY=${CROSS_COMPILE}objcopy"
    "OBJDUMP=${CROSS_COMPILE}objdump"
    "READELF=${CROSS_COMPILE}readelf"
    "STRIP=${CROSS_COMPILE}strip"
)

echo "=== Configure X657B ARM64 ==="
make -C "$ROOT" "${MAKE_ARGS[@]}" "$DEFCONFIG"
make -C "$ROOT" "${MAKE_ARGS[@]}" olddefconfig

for option in CONFIG_ARM64 CONFIG_COMPAT CONFIG_MACH_MT6761 CONFIG_MODVERSIONS; do
    grep -qx "$option=y" "$OUT/.config" || {
        echo "ERROR: required option $option is not enabled" >&2
        exit 1
    }
done

echo "=== Build ARM64 Image and in-tree modules ==="
make -C "$ROOT" -j"$JOBS" "${MAKE_ARGS[@]}" Image modules

DIST="$OUT/dist"
mkdir -p "$DIST"
cp "$OUT/arch/arm64/boot/Image" "$DIST/Image"
gzip -n -9 -c "$DIST/Image" > "$DIST/Image.gz"
cp "$OUT/.config" "$DIST/config"
cp "$OUT/Module.symvers" "$DIST/Module.symvers"
cp "$OUT/include/config/kernel.release" "$DIST/kernel.release"

{
    printf 'Git commit: %s\n' "$(git -C "$ROOT" rev-parse HEAD)"
    printf 'Kernel release: %s\n' "$(cat "$DIST/kernel.release")"
    printf 'Compiler: %s\n' "$("$CC" --version | head -n 1)"
    printf 'Image SHA-256: %s\n' "$(sha256sum "$DIST/Image" | awk '{print $1}')"
    printf 'Image.gz SHA-256: %s\n' "$(sha256sum "$DIST/Image.gz" | awk '{print $1}')"
    printf 'Module.symvers SHA-256: %s\n' "$(sha256sum "$DIST/Module.symvers" | awk '{print $1}')"
    printf 'Config SHA-256: %s\n' "$(sha256sum "$DIST/config" | awk '{print $1}')"
} > "$DIST/BUILD-MANIFEST.txt"

(
    cd "$DIST"
    sha256sum Image Image.gz config Module.symvers kernel.release > SHA256SUMS
)
tar -czf "$DIST/x657b-arm64-kernel-build.tar.gz" -C "$DIST" .

echo "=== Verified build outputs ==="
cat "$DIST/BUILD-MANIFEST.txt"
ls -lh "$DIST/Image" "$DIST/Image.gz" "$DIST/Module.symvers" "$DIST/x657b-arm64-kernel-build.tar.gz"
echo "SUCCESS: ARM64 Image and in-tree modules built."
