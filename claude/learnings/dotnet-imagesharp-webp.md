# Encoding WebP in .NET from System.Drawing.Bitmap via SixLabors.ImageSharp

Pipeline used in crop-stage's `ScreenshotCapture`: capture with GDI+ →
LockBits → byte[] → ImageSharp.Image.LoadPixelData<Bgra32> → WebpEncoder.

## Settings (matches toolbox/image_opt's defaults)
- `Quality = 60`
- `Method = WebpEncodingMethod.BestQuality` (= 6, slowest, smallest file)
- `FileFormat = WebpFileFormatType.Lossy`

## Pixel format
`Format32bppArgb` stores as BGRA in little-endian byte order, matching
ImageSharp's `Bgra32`. Direct buffer copy works without channel reordering.

## Stride handling
`Bitmap.LockBits` returns a stride that may include row padding. Compare
`data.Stride` to `width * 4`; if equal, a single `Marshal.Copy` works;
otherwise copy row-by-row.

```csharp
var rect = new Rectangle(0, 0, bmp.Width, bmp.Height);
var data = bmp.LockBits(rect, ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
try
{
    var rowBytes = bmp.Width * 4;
    var bytes = new byte[rowBytes * bmp.Height];
    if (data.Stride == rowBytes)
    {
        Marshal.Copy(data.Scan0, bytes, 0, bytes.Length);
    }
    else
    {
        for (var row = 0; row < bmp.Height; row++)
            Marshal.Copy(IntPtr.Add(data.Scan0, row * data.Stride),
                         bytes, row * rowBytes, rowBytes);
    }
    using var image = SixLabors.ImageSharp.Image.LoadPixelData<Bgra32>(
        bytes, bmp.Width, bmp.Height);
    var encoder = new WebpEncoder
    {
        Quality = 60,
        Method = WebpEncodingMethod.BestQuality,
        FileFormat = WebpFileFormatType.Lossy,
    };
    using var fs = File.Create(targetPath);
    image.Save(fs, encoder);
}
finally { bmp.UnlockBits(data); }
```

## Namespace pitfall
`using SixLabors.ImageSharp;` brings `Image`, `Size`, `Rectangle` into
scope — collides with `System.Drawing.{Image,Size,Rectangle}`. Two
workarounds:

1. **Skip the using** (used in crop-stage). Fully qualify
   `SixLabors.ImageSharp.Image.LoadPixelData<>` and call
   `image.Save(FileStream, encoder)` with `using var fs = File.Create(path)`.
   Avoids needing the `ImageExtensions.Save(string)` extension method, which
   is the only reason you'd want the root namespace imported.
2. **Type aliases**: `using ImageSharpImage = SixLabors.ImageSharp.Image;`
   and similar for the colliding types. More verbose.

## NuGet and licensing
Five advisories published in 2026 (GHSA-jjfr-hcj7-qf5w, GHSA-j3p4-wp97-rph4,
GHSA-j9gm-c75j-xc9q, GHSA-wmxv-xphr-5c9g, GHSA-gwg2-r3hj-4w44) affect every release
through 3.1.12 and 4.0.0 through 4.1.1. They are fixed in 3.2.0 on the 3.x line and in
4.1.2 on 4.x, so use one of those or later. The global advisory database lists only
4.1.2 as patched and counts 3.2.0 as vulnerable; the repository advisories on
SixLabors/ImageSharp carry both fixed versions.

Both fixed releases enforce a Six Labors license, so staying on 3.x does not avoid it.
The package's `SixLabors.ImageSharp.targets` runs a `SixLabors_ValidateLicense` target
before `CoreCompile`, which fails with `No Six Labors license found`; design-time builds
skip it. In 3.2.0 and from 4.1.0 the task runs with
`ContinueOnError="$(Configuration.StartsWith('Debug'))"`: a configuration whose name
starts with `Debug` gets a warning and keeps building, and every other configuration,
Release included, fails. 4.0.0 fails in Debug too.

- **Getting a key:** an open-source or source-available project on a recognised public
  code host qualifies for the free Community license at licensing.sixlabors.com. Choose
  kind `OpenSource` and list the exact `AssemblyName` of every project that directly
  references a Six Labors package, test projects included: case-sensitive, without
  `.dll` or `.csproj`, and the project filename where no `AssemblyName` is set. Eligible
  open-source projects get the key automatically, as a `sixlabors.lic` file. The one key
  observed so far expires 455 days after issue (a year plus the 90-day renewal window);
  its `ExpiryDateUtc` field holds the real date. Renew by resubmitting the form from the
  same email address, with the assembly names again, in the final 90 days.
- **Committing it:** a key whose `Key=` field begins `Assembly:` is scoped to the named
  assemblies. Each name is part of the signed data, so a project whose `AssemblyName` is
  missing from the key, or differs by case, fails validation. Six Labors' docs say such a
  key "can be committed to a public repository", while unrestricted community keys and
  commercial keys must stay private. A committed assembly-scoped key lets CI build with
  no secret.
- **Where the build looks:** setting `SixLaborsLicenseKey` turns off both file lookups.
  Otherwise `SixLaborsLicenseFile` is used if set, and failing that the targets glob
  `**/sixlabors.lic` from the *project* directory downward. A file at the repo root is
  therefore invisible to a project in `src/`, and two matches fail with
  `Multiple Six Labors license files found`. Build the explicit path from
  `$(MSBuildThisFileDirectory)`, the directory of the file that declares it: from a root
  `Directory.Build.props`, `$(MSBuildThisFileDirectory)sixlabors.lic`; from a project
  file directly under `src/`, `$(MSBuildThisFileDirectory)..\sixlabors.lic`.
- **Key passed on the command line:** escape every `;` in
  `-p:SixLaborsLicenseKey=…`. Left bare, MSBuild silently cuts the value at the first
  semicolon and the task receives only the `Id=…` part. Six Labors' docs prescribe
  `%253B`; 3.2.0 and 4.1.x unescape the value once more, so `%3B` works there too, while
  4.0.0 accepts only `%3B`. Putting
  `<SixLaborsLicenseKey>$(SIXLABORS_LICENSE_KEY)</SixLaborsLicenseKey>` in the project and
  the unescaped key in that environment variable needs no escaping at all.
