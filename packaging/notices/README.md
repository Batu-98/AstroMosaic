# Supplemental Windows notices

The collector copies notices present in the installed wheels. The files here supplement those notices for the specified upstream versions. When updating a dependency or the Python build, compare the collected notices and replace the matching supplements as needed.

| Build input | Upstream notice files |
| --- | --- |
| SEP 1.4.1 | [SEP license directory](https://github.com/sep-developers/sep/tree/v1.4.1/licenses) |
| Seiza 0.48.2 | [Apache-2.0 license](https://github.com/theatrus/seiza/blob/v0.48.2/LICENSE) |
| Qt for Python 6.12.0 and the software renderer | [LGPL-3.0-only license](https://github.com/pyside/pyside-setup/blob/v6.12.0/LICENSES/LGPL-3.0-only.txt), [Mesa 11.2.2 source archive](https://archive.mesa3d.org/older-versions/11.x/11.2.2/), [LLVM 3.6.2](https://releases.llvm.org/3.6.2/LICENSE.TXT) |
| CPython 3.13.18 release build | [OpenSSL 3.5.9](https://github.com/openssl/openssl/blob/openssl-3.5.9/LICENSE.txt), [Tcl 8.6.15](https://github.com/tcltk/tcl/blob/core-8-6-15/license.terms), [Expat 2.9.0](https://github.com/libexpat/libexpat/blob/R_2_9_0/expat/COPYING), [zlib 1.4](https://github.com/madler/zlib/blob/v1.4/LICENSE), [Python Build Standalone 20261110 notices for libffi, liblzma and mpdecimal](https://github.com/astral-sh/python-build-standalone/tree/20261110) |

The CPython supplements match the versions reported by the standalone Windows build used for release preparation. The collector also copies the Python license from the actual build environment and the Tk notice if supplied there.
