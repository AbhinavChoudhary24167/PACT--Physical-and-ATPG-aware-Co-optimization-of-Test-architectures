# Isolated Stage-A external-generator build audit

This recovery preserves the incomplete seal at `a8a99c43e963d87289c8e35161a81be151e545bd` and its receipt at `8df6834bdcb3b18570ca9a27e27599bd688d097f`. New execution receipts live under `recovery_20261003/`; no frozen protocol, P0 source, B0/B1 architecture, selection policy or historical measurement is replaced.

## Isolation and provisioning

The build base is the existing immutable Docker image `openroad/orfs@sha256:f05cee3219a02f26289f02f00e11a3fc986ab51a482a0000a2da810cda219a6e`, Ubuntu 22.04.5, amd64. Its existing SWIG and Tcl development packages are provisioned by selecting that content-addressed image, rather than installing into the qualified WSL system. The image inspection, layer identities and executable/header/library SHA256s are retained in `recovery_20261003/toolchain_image.json` and `toolchain/qualification.json`.

Fresh sources, build directories and an additional dependency prefix use a dedicated 16-GiB ext4 image on D:, mounted in WSL at `/mnt/pact-oss-recovery` and inside the container at `/build_storage`. This avoids writing build products into the qualified environment and gives native Linux filesystem behavior. The original downloaded archives remain on D:. The repository is mounted read-only at `/workspace`. Build containers have network access disabled; dependency acquisition happens separately and records immutable revisions/archive hashes.

Storage recovery: WSL dropped the initial short-lived loop mount between invocations. Initial dependency installation and part of the B2 compilation therefore temporarily used the dedicated prefix on WSL's root filesystem. Compilation was intentionally paused, without a compiler error or source patch. `pact_oss_storage.py` copies and hashes every partial-build file onto the D: image, verifies the remounted copy, and removes only that verified generated fallback. Every later build/generation invocation restores and verifies the loop device's exact D: backing file before accessing the prefix. `storage_relocation.json` retains the complete copy verification; the initial mount attempt and first interrupted build remain preserved. Source semantics, dependency versions, container paths and compiler flags are unchanged by relocation.

The fixed downstream `/usr/bin/openroad` still has SHA256 `fcd7dcfc37d329bd43a7ede75805319a2e70e6879da11d42b4fd1c2e50e645c3`. ORFS and the PACT Python environment are unchanged. The image's OpenROAD/ORFS executables are not downstream implementation backends.

## Requirements audited before B2 configuration

Requirements below come from the exact B2 source and pinned OpenSTA/slang submodules. Minimums are distinguished from the versions recommended by `etc/DependencyInstaller.sh`. GUI, GPU and tests are disabled for these generator builds. B3 will be audited against its own pinned source after B2 architecture qualification.

| Dependency | Actual requirement / source | Detected and provisioned version | Container installation / resolved path |
|---|---|---|---|
| CMake | Root >=3.16; CMP0144 needs >=3.27; pinned slang >=3.25 | 3.31.9 | `/usr/local/bin/cmake` |
| C/C++ compiler | C++20; root GCC >=8.3 check | GCC/G++ 11.4.0; unwrapped compiler explicitly selected | `/usr/bin/gcc`, `/usr/bin/g++` |
| SWIG | >=4.3, `src/CMakeLists.txt:124` | 4.3.0 | `/usr/local/bin/swig`; data `/usr/local/share/swig/4.3.0` |
| Tcl development pair | Real Tcl 8.x header and library, custom `cmake/FindTCL.cmake` | Header/runtime 8.6.12; `tcl8.6-dev` 8.6.12+dfsg-1build1 | `/usr/include/tcl8.6/tcl.h`; `/usr/lib/x86_64-linux-gnu/libtcl8.6.so`; `/usr/bin/tclsh` |
| Boost | >=1.78 in `src/utl/CMakeLists.txt`; slang seeks >=1.87; iostreams, serialization, thread | 1.89.0 | `/usr/local/lib/cmake/Boost-1.89.0`; headers `/usr/local/include` |
| Eigen | `find_package(Eigen3 REQUIRED)`; installer recommends 3.4 | 3.4.0 | `/opt/or-tools/share/eigen3/cmake` |
| Bison | >=3.2 in pinned OpenSTA; OpenDB parser also requires it | 3.8.2 | `/usr/bin/bison` |
| Flex | OpenSTA `find_package(FLEX)`; installer recommends 2.6.4 | 2.6.4 | `/usr/bin/flex` |
| Python development | `find_package(Python3 COMPONENTS Development REQUIRED)`; slang also needs interpreter | 3.10.12 | `/usr/bin/python3.10`; `/usr/include/python3.10`; `/usr/lib/x86_64-linux-gnu/libpython3.10.so` |
| spdlog | `src/CMakeLists.txt:219`; installer recommends 1.15.0 | 1.15.0 | `/usr/local/lib/cmake/spdlog` |
| fmt | Pinned slang `external/CMakeLists.txt` requires >=12.1; root requires CONFIG package | 12.1.0, independently built from `407c905e45ad75fc29bf0f9bb7c5c2fd3475976f` | `/build_storage/toolchain/lib/cmake/fmt` |
| Abseil | `src/CMakeLists.txt:130`; match OR-Tools bundled version | 20250512 | `/opt/or-tools/lib/cmake/absl` |
| OR-Tools | GPL/PAR/MPL require it; installer recommends 9.14.6206 | 9.14.6206 | `/opt/or-tools/lib/cmake/ortools` |
| LEMON | STT/GPL/CTS/DPL require it; installer recommends 1.3.1 | 1.3.1 image dependency; resolution independently passes | `/usr/local/share/lemon/cmake`; `/usr/local/lib/libemon.a` |
| CUDD | Pinned OpenSTA `cmake/FindCUDD.cmake`; installer recommends 3.0.0 | Real header/archive present; finder/header do not export a version, so the installed version remains unverified | `/usr/local/include/cudd.h`; `/usr/local/lib/libcudd.a`; immutable image binding |
| yaml-cpp | OpenDB 3dblox `find_package(yaml-cpp REQUIRED)` | 0.7.0 | `/usr/lib/x86_64-linux-gnu/cmake/yaml-cpp` |
| zlib | OpenDB LEF/DEF parsers; OR-Tools transitive dependency | 1.3.1 resolved from OR-Tools | `/opt/or-tools/include`; `/opt/or-tools/lib/libz.so` |
| OpenMP / threads | ANT/GPL/GRT/DRT and shared utility targets | OpenMP 4.5 / pthread test passes | GCC runtime; CMake discovery records retained |
| OpenGL | `src/gui/CMakeLists.txt:10` requires discovery even with `BUILD_GUI=OFF` | Actual B2 CMake discovery passes | `/usr/lib/x86_64-linux-gnu/libGL.so`; headers `/usr/include` |
| Qt / Tk | Qt discovery is QUIET; GUI disabled; custom Tcl finder does not require Tk | Optional/excluded from GUI generation | No additional GUI provisioning |
| GTest | Root `ENABLE_TESTS=OFF`; OpenSTA separately defaults `BUILD_TESTS=ON` and requires GTest during configuration | 1.17.0, actually found by B2 CMake; explicit `openroad` target does not build the test suite | `/usr/local/lib/cmake/GTest` |
| GPU libraries / mimalloc | GPU/slang mimalloc disabled | Excluded | No additional provisioning |
| OpenSTA, ABC, slang-elab, nested slang/fmt | Exact saved submodule commits, not system replacements | Existing immutable saved archive pins | `baselines/B2_openroad_10176/build_sources.json`; fresh source extraction verified against those archives and pinned source Git blobs |

OR-Tools' own transitive packages are resolved from its existing prefix. The independent package probe initially discovered a Boost-root collision: OR-Tools exported Boost 1.87 while the complete iostreams/serialization/thread packages were 1.89. An explicit `Boost_DIR=/usr/local/lib/cmake/Boost-1.89.0` resolves the consistent installed package family. The failed and successful probe logs are both preserved. This is build dependency selection, with no PR source modification.

The compiler logs also show transitive Boost headers under `/opt/or-tools/include/boost` in some targets. Thus CMake's Boost package/library selection is 1.89, while the existing OR-Tools prefix can contribute its bundled 1.87 headers through target include order. The exact logs and immutable image preserve this distinction; the audit does not claim that every compiler include came from `/usr/local/include`. Any actual compile/link incompatibility must be diagnosed before accepting the build.

## Independent prerequisite gate

Before retrying B2, `pact_oss_toolchain_probe.py` configured a separate prerequisite-only project using the pinned source's actual Tcl finder and `find_package(SWIG 4.3 REQUIRED)`. It compiled and linked a C program using the resolved Tcl header/library, checked header/runtime version equality, initialized Tcl and evaluated an expression. It also generated a Tcl binding with the resolved SWIG, compiled the shared module against those development files, loaded it in Tcl and obtained the expected result.

The probe passed with `SWIG_EXECUTABLE=/usr/local/bin/swig`, `SWIG_VERSION=4.3.0`, `SWIG_DIR=/usr/local/share/swig/4.3.0`, `TCL_HEADER=/usr/include/tcl8.6/tcl.h`, `TCL_INCLUDE_PATH=/usr/include/tcl8.6`, and `TCL_LIBRARY=/usr/lib/x86_64-linux-gnu/libtcl8.6.so`. Matching header/runtime version: **8.6.12**. A working `tclsh` alone was not accepted.

The broader separate package probe passed after fmt provisioning and explicit Boost selection. Its `dependency_qualification.json`, CMakeCache and logs retain the exact dependency resolution before any B2 configuration. Actual B2 configuration must additionally retain its own CMakeCache, log and resolved dependency receipt; independent probe resolution is not substituted for the OpenROAD configuration record.

## B2 reproduced and qualified

B2 compiled successfully without a PR source patch. Binary: `/build_storage/B2_openroad_10176/build/bin/openroad` (host `/mnt/pact-oss-recovery/B2_openroad_10176/build/bin/openroad`), SHA256 `601da32f4493cd9587b53812385af4ec9ed08f1c3f5e9def9c6a7e4897b25087`. The successful resumed build took 5213.271 seconds, in addition to the earlier intentional storage pause. Root LTO was disabled; OpenSTA internally enabled LTO, producing 84 serial LTRANS partitions at the final link. The linker retained a nonfatal warning about OR-Tools' `libbz2.so.1` versus system `libbz2.so.1.0`; all three subsequent B2 runtime/architecture qualifications passed.

The binary advertises `+GPU`; the pinned root `CMakeLists.txt:236` unconditionally defines the banner's `GPU` macro. This is distinct from `ENABLE_GPU=OFF`, which excludes Kokkos/CUDA/HIP discovery and GPU compute backends. The scan optimizer used here is the CPU implementation. BZip2 is an actual transitive dependency resolved by CMake at `/opt/or-tools/lib/libbz2.so` (reported version 1.1.0); its link warning is preserved rather than suppressed.

The compiled command probe verified Tcl exposure and linked `Dft::scanOpt()` / `OptimizeScanWirelength2Opt` symbols before generation. Source-bound default: 30 iterations, with external endpoints included. Actual `execute_dft_plan; scan_opt` runs qualified exact K=2 inventories and unchanged endpoint geometry on s5378 (90/89), s9234 (106/105), and s15850 (267/267). No B1 architecture was regenerated.

## B3 requirements audit before configuration

B3's full archive and all five recursive submodules have now been acquired from immutable commits. Its OpenSTA pin is `244797f162b465751912b651d55d9854296aa745`; ABC/slang-elab/nested fmt/slang pins match B2. All saved B3 source blobs match the fresh extraction. `requirements_inventory.json` binds the complete CMake requirement files. The custom Tcl finder is byte-identical to the independently probed B2 finder. Root/src/OpenSTA CMake files were compared before configuration: OpenSTA's CMake requirements are identical; root still uses C++20 and the same dependency minimums; SWIG remains >=4.3; pinned slang still requires fmt >=12.1. B3 also adds `tst` unconditionally, so its GTest fixture target depends on the already provisioned GTest package even with root tests disabled. No extra package installation is needed on the current evidence.

B3 uses the same immutable image, verified development header/library pair, explicit Boost/fmt prefixes, and unwrapped GCC/G++ 11.4. Compiler and LTO temporary files are explicitly directed to `/build_storage/B3_openroad_10666/compiler_tmp` on D: to avoid consuming WSL's C:-backed writable container layer. The build command records that `TMPDIR`; this changes temporary storage only.

B3 configuration passed in 16.209 seconds. Its own CMakeCache and resolved-dependency receipt independently confirm the same SWIG executable/version and Tcl development paths. This older root reports the supplied `ENABLE_GPU` variable as unused; its source has no B2 Kokkos backend option. The unused-variable warning is retained in the configuration log. No GPU package was provisioned or substituted for scan optimization.

## B3 compilation stop: pinned source API defect

B3 compilation exited 2 after 4178.934 seconds (1:09:38), with maximum child RSS 2,095,732 kbytes. The optimizer static library compiled, but no OpenROAD executable was produced. That partial library is not accepted as compiled-command or architecture qualification.

The exact pinned `src/dft/src/cells/OneBitScanCell.cpp:106` calls `getLibertyScanIn(test_cell_)` without a receiver; line 111 similarly calls `getLibertyScanOut(test_cell_)`. GCC reports both names undeclared. The already included `src/dbSta/include/db_sta/dbNetwork.hh:436–437` declares these as `sta::dbNetwork` member functions. The same translation unit correctly uses `db_network_->getLibertyScanIn(...)` and `db_network_->getLibertyScanOut(...)` in its existing connection/accessor methods. Neither `OneBitScanCell` nor its `ScanCell` base declares the unqualified functions. The pinned OpenSTA and DFT sources provide no free-function alternatives.

This is a source API/name-lookup defect in revision `746c748b19cd2b9d7fb6aa3afe53fe4c31ce3656`, rather than another missing package. Repair would require changing the two calls or injecting equivalent source behavior through compiler flags. Under the user's explicit source-patch stop rule, no such change or build retry was performed. Full source hashes, declaration snapshots, compiler flags/rule, diagnostics and resource receipts are retained in the versioned recovery evidence. No B3 architecture exists, and no new physical implementation, extraction or simulation occurred. Stage A remains incomplete and the scientific result inconclusive.

OR-Tools' resolved transitive packages also include re2 11.0.0, Clp 1.17.10, Cbc 2.10.12 and SCIP 9.2.2 under `/opt/or-tools/lib/cmake/`; these are supplied by the immutable image. Tcl Extended is explicitly disabled by this configuration despite the independent OpenSTA cache option, and requires no extra package for the `openroad` target.

## Source and scientific boundaries

B2 remains `6fff875551fe13a2aae3a22f871a6ca7f8d5c1cf`; B3 remains `746c748b19cd2b9d7fb6aa3afe53fe4c31ce3656`. No algorithm source patch is authorized. If compilation cannot be repaired through environment/build configuration alone, stop and report the incompatibility. No B3 build occurs before B2 canonical K=2 qualification. No physical implementation occurs before both generators qualify. No Stage-B/P1 work occurs in this recovery.
