# References / 参考资料

This file records the references actually used by the project, and separates
creative inspiration from code or data that is used directly.

本文件记录项目实际使用的参考资料，并区分“创意来源”和“直接使用的代码/数据”。

## Creative background / 创意背景

| Source | Use |
| --- | --- |
| [IOCCC](https://www.ioccc.org/) | Background for source-code art and obfuscated C. No IOCCC entry code is copied. |
| [Andy Sloane, donut.c / Donut math](https://www.a1k0n.net/2011/07/20/donut-math.html) | Creative inspiration for “source code as a picture”. This project lays out source text at compile time; it does not use donut.c's code, math, or runtime rendering. |

## C tokenization and compilation / C 词法与编译

| Source | Use |
| --- | --- |
| [GCC: Tokenization](https://gcc.gnu.org/onlinedocs/cpp/Tokenization.html) | Reference for preprocessing tokens, comments and line splicing used by A/D/E. |
| [GCC: Initial processing](https://gcc.gnu.org/onlinedocs/cpp/Initial-processing.html) | Reference for translation phases, line splicing and trigraphs. |
| [GCC: Overall options](https://gcc.gnu.org/onlinedocs/gcc/Overall-Options.html) | Reference for `-c`, `-std=c11` and object compilation without linking. |
| [Clang: CINDEX](https://clang.llvm.org/doxygen/group__CINDEX.html) | The raw lexer and source-analysis API used by A. |

## Font and runtime / 字体与运行环境

| Source | Use |
| --- | --- |
| [Roboto Mono](https://github.com/googlefonts/RobotoMono) | Bundled preview font (`codeart/web/fonts/RobotoMono-Regular.ttf`). |
| [SIL Open Font License 1.1](https://openfontlicense.org/) | License for the bundled Roboto Mono font; the local copy is `codeart/web/fonts/OFL.txt`. |
| [Python](https://www.python.org/) | Implementation language. |
| [libclang 18.1.1](https://pypi.org/project/libclang/18.1.1/) | Pinned Python binding used by A/E. |
| [pytest 9.2.0](https://pypi.org/project/pytest/9.2.0/) | Development test runner. |

## Not used / 未使用

The project does not use Pillow, Streamlit, donut.c's rendering algorithm, or
any third-party bitmap font. The CODE glyphs are the fixed 5×7 table in
`codeart/shapes.py`.
