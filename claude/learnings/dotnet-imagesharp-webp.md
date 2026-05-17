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

## NuGet
`dotnet add package SixLabors.ImageSharp` — version 3.x is current.
