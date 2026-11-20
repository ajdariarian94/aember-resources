# AEMBER RESOURCES

Build inputs and tooling for the low-level pieces of **Aember**, a lightweight
embedded-Linux system:

| Component | Recipe                                             | Artifact                                                      |
|-----------|----------------------------------------------------|---------------------------------------------------------------|
| Kernel    | `meta-aember/recipes/kernel/aember-kernel.bb`      | Linux 6.16 image, `System.map`, `Module.symvers`, modules     |
| BusyBox   | `meta-aember/recipes/busybox/aember-busybox.bb`    | static BusyBox 1.36.1                                         |
| LXC       | `meta-aember/recipes/virtualization/aember-lxc.bb` | LXC 6.0.2 tools, `liblxc.so`, headers, relocatable `lxc.pc`   |
| SDK       | `core-image-minimal -c populate_sdk`               | Poky cross toolchain (GCC 15, C++23) and target sysroot       |

for four architectures, plus opt-in musl variants:

| Architecture         | Machine         | Tune             | Runs on |
|----------------------|-----------------|------------------|---------|
| `x64-poky-linux`     | `x64-linux`     | `core2-64`       | PCs, QEMU |
| `aarch64-poky-linux` | `arm64-linux`   | `cortexa53`      | every 64-bit Arm board: Raspberry Pi 3/4/Zero 2 W, i.MX8, Rockchip, QEMU `virt` |
| `arm-poky-linux`     | `arm-linux`     | `armv7athf-neon` | ARMv7-A boards (Cortex-A7/A9/A15), QEMU `virt` |
| `riscv64-poky-linux` | `riscv64-linux` | `riscv64` (RV64GC) | QEMU `virt`, StarFive VisionFive 2, Milk-V |
| `x64-poky-linux-musl` | `x64-linux` + musl | `core2-64` | as x64; musl C library (smaller images, no sanitizers) |
| `aarch64-poky-linux-musl` | `arm64-linux` + musl | `cortexa53` | as aarch64, with musl |
| `arm-poky-linux-musl` | `arm-linux` + musl | `armv7athf-neon` | as arm32, with musl (musleabi hard-float) |
| `riscv64-poky-linux-musl` | `riscv64-linux` + musl | `riscv64` | as riscv64, with musl |

The SDKs also carry GCC's sanitizer runtimes (libasan, libubsan; liblsan and
libtsan where GCC has them), for aember's sanitizer test builds.

Builds are described with [kas](https://kas.readthedocs.io/) and run inside a
digest-pinned kas container, so every machine builds in the same environment.

## Getting started

1. On the host, run `tools/scripts/prerequisites.sh` (it checks Docker, Git,
   VS Code and writes `tools/scripts/.env`).
2. Open the repo in VS Code and choose **Reopen in Container**.
3. In the dev container, run:

```bash
aember build kernel busybox lxc --arch x64-poky-linux
```

The first build compiles the whole toolchain and takes a while. Later builds
reuse `yocto/sstate-cache` and finish in minutes.

Artifacts are written to `yocto/build/<arch>/`:

```
yocto/build/x64-poky-linux/
├── kernel/          bzImage, System.map, Module.symvers, kernel-build-manifest.txt, lib/modules/<kver>/
├── busybox/         busybox, busybox-build-manifest.txt
├── virtualization/  lxc-*, libs/liblxc.so*, include/lxc/, pkgconfig/lxc.pc, etc-lxc/
└── sdk/             installed Poky SDK (aember build sdk)
```

## Commands

```bash
aember --help                                    # all commands
aember build <component>... [-a <arch>] [-f]     # kernel | busybox | lxc | sdk
aember kas-shell <component> [-a <arch>] [-c "<cmd>"]   # bitbake shell in the kas container
aember lint                                      # ruff, black, clang-format, cmake-format
aember -v ...                                    # verbose logging
```

## How it works

### kas

A component build is always a chain of three kas files:

```
kas/base.yml : kas/machine/<machine>.yml : kas/recipes/<component>.yml
```

- `kas/base.yml` sets the distro (`poky`) and the shared `local.conf`, and pins
  Poky to an exact commit. It adds `meta-aember` from this repo.
- `kas/machine/*.yml` selects the machine.
- `kas/recipes/*.yml` selects the bitbake target (and task).

### Build container

`aember` runs kas through `docker run` with
`ghcr.io/siemens/kas/kas:5.4@sha256:…` (Debian 13), mounting the repo at
`/work`. The dev container reaches Docker through the host socket, so the
mount uses `HOST_ROOT_PATH`, which is set by `devcontainer.json`. Don't run
bitbake directly in the dev container: its Ubuntu 26.04 / glibc 2.43 host
breaks Poky's host tools.

### Content-addressed caching

Every artifact is identified by a **CAS key**: the sha256 of the kas image
reference, its kas chain and every file in `meta-aember/`. `aember build`:

1. skips if `yocto/build/<arch>/<component>/.kas-hash` matches the key,
2. downloads `aember-<component>-<arch>-v<VERSION>.tar.gz` from the GitHub
   release `v<VERSION>` if `hashes/<arch>/<component>.sha256` matches the key,
3. otherwise builds with kas and copies the result from bitbake's deploy dir
   (`tmp/deploy/images/<machine>/aember/<component>/`).

Changing a recipe, a kas file, the Poky commit or the kas image changes the
key, so only affected artifacts are rebuilt. Only commit a
`hashes/<arch>/<component>.sha256` together with its published release asset.

## Repository layout

```
.devcontainer/   dev container (Ubuntu 26.04)
aember-cli/      the `aember` CLI (Python, Typer)
kas/             kas configuration
meta-aember/     Yocto layer: machines and recipes
hashes/          CAS keys of released artifacts
tools/scripts/   container init and host setup scripts
VERSION          release version
yocto/           (git-ignored) kas work dir: poky, bitbake, downloads, sstate, artifacts
```

See [AGENTS.md](AGENTS.md) for detailed conventions, which also serves as the
guide for AI coding agents.

## CI

GitHub Actions (`.github/workflows/ci.yml`) runs the CLI's tests (including
the check that every architecture is complete: machine, kas file, kernel,
BusyBox and LXC configuration, recipes, SDK maps) and lint on every push and
pull request. The Yocto builds themselves are too big for a hosted runner.
