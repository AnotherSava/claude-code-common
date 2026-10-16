# Writing minimal PE files as test fixtures

Code that reads PE metadata (import tables, version info) is testable without shipping real binaries: a test can write a one-section 64-bit PE that Windows' own APIs accept. A working generator is `tests/PeFixture.cs` in the achievement-overlay repo; the layout facts below are what it took.

## Layout that `PEReader` and `GetFileVersionInfo` both accept

- DOS header with `MZ` and `e_lfanew = 0x40`; `PE\0\0` at 0x40; COFF header (`Machine = 0x8664`, one section, `SizeOfOptionalHeader = 240`).
- PE32+ optional header (`Magic = 0x20B`): `ImageBase` at +24 (8 bytes), `SectionAlignment` +32, `FileAlignment` +36, subsystem versions +48, `SizeOfImage` +56, `SizeOfHeaders` +60, `Subsystem` +68, the four 8-byte stack/heap sizes from +72, `NumberOfRvaAndSizes = 16` at +108, data directories from +112 (import = 1, resource = 2, delay import = 13).
- One section at file offset 0x200 / RVA 0x1000 holding everything: import descriptors (5 ints, name RVA 4th, all-zero terminator), delay descriptors (8 ints: attributes with bit 0 = "names are RVAs", then the name), the resource tree, and any marker bytes a test greps for.
- An entry point of 0 and no code are fine: `GetFileVersionInfo` maps the file as a datafile, and `System.Reflection.PortableExecutable.PEReader` only reads headers and sections.

## RT_VERSION resource

Tree of three directory levels (type 16 → id 1 → language 0x409), each a 16-byte header with one id entry (high bit on the offset = subdirectory), then a 16-byte data entry whose `OffsetToData` is an **RVA**, not a section offset. The data is `VS_VERSIONINFO`: every block is `wLength, wValueLength, wType`, a UTF-16 key, padding to 4, value, children each padded to 4. `wValueLength` counts **words** for string values, bytes for binary ones. Include `VarFileInfo\Translation` (`09 04 B0 04`).

## The `FileVersionInfo` trap

.NET's `FileVersionInfo` accepts a string table only when it yields a non-empty **`FileVersion`**. Without one it tries the next code pages (`040904B0`, `040904E4`, `04090000`), and each attempt overwrites `CompanyName` and the rest, so a table holding only `CompanyName` reads back as `""` while `Language` is filled in. `pefile` parses the same file correctly, which makes it look like a Windows-side bug. Always write `FileVersion`.

## Prove the fixture, not just the subject

Assert the fixture round-trips through the real API first (`FileVersionInfo.GetVersionInfo(path).CompanyName`, the import reader), in its own test; otherwise a malformed fixture makes rule tests fail for the wrong reason, or pass for one.
