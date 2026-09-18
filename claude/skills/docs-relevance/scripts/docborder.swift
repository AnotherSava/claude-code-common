// docborder — stroke a hairline frame around a screenshot.
//
// A dark screenshot on a dark documentation page has no edge: the window's own
// background and the page background are the same colour, so the reader cannot
// see where the picture stops. macOS gives a *decorated* window a light 1px
// stroke and transparent rounded corners for free, which is why a shot of one
// already reads correctly — but an undecorated window (this project's widget)
// has neither, and a region capture never does.
//
// Deliberately a plain command-line binary rather than another flag on DocShot:
// this needs no TCC permission at all, and rebuilding DocShot would invalidate
// the Screen Recording grant pinned to its signature. Framing at capture time,
// not retouching — it adds an edge the OS would have drawn on a decorated
// window, and changes no pixel of the content.
import Foundation
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers

func die(_ m: String) -> Never {
    FileHandle.standardError.write(("docborder: " + m + "\n").data(using: .utf8)!)
    exit(2)
}
let args = Array(CommandLine.arguments.dropFirst())
func opt(_ n: String) -> String? {
    guard let i = args.firstIndex(of: n), i + 1 < args.count else { return nil }
    return args[i + 1]
}

guard let inPath = opt("--in") else { die("need --in <png>") }
let outPath = opt("--out") ?? inPath
// Light grey by default: the same value macOS strokes a window frame with, so a
// bordered undecorated window sits beside a decorated one without looking edited.
let hex = (opt("--color") ?? "BDBDBD").trimmingCharacters(in: CharacterSet(charactersIn: "#"))
guard hex.count == 6, let rgb = Int(hex, radix: 16) else { die("--color wants RRGGBB") }
// Widths and radii are in *pixels* of the source, which is already 2x on a
// Retina capture — so a 1pt-looking hairline is the default 2.
let lineW = Double(opt("--width").flatMap { Double($0) } ?? 2)
let radius = Double(opt("--radius").flatMap { Double($0) } ?? 0)

guard let src = CGImageSourceCreateWithURL(URL(fileURLWithPath: inPath) as CFURL, nil),
      let img = CGImageSourceCreateImageAtIndex(src, 0, nil) else { die("cannot read \(inPath)") }
let w = img.width, h = img.height

guard let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: 0,
                          space: CGColorSpace(name: CGColorSpace.sRGB)!,
                          bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else {
    die("cannot create a drawing context")
}
// With a radius, the corners are *clipped away* as well as stroked — the
// context starts fully transparent, so anything outside the rounded path simply
// never gets drawn. That is what gives a region crop the transparent corners a
// decorated window brings for free: a crop is a rectangle of screen pixels and
// has no alpha of its own, but nothing stops us writing it.
let outer = CGRect(x: 0, y: 0, width: Double(w), height: Double(h))
if radius > 0 {
    ctx.addPath(CGPath(roundedRect: outer, cornerWidth: radius, cornerHeight: radius, transform: nil))
    ctx.clip()
}
ctx.draw(img, in: outer)
ctx.resetClip()

// Inset by half the stroke so the whole line lands inside the image — stroked on
// the boundary, half of it would fall outside and the frame would read thinner
// on two sides than the other two.
let inset = lineW / 2
let rect = CGRect(x: inset, y: inset, width: Double(w) - lineW, height: Double(h) - lineW)
let path = radius > 0
    ? CGPath(roundedRect: rect, cornerWidth: radius, cornerHeight: radius, transform: nil)
    : CGPath(rect: rect, transform: nil)
ctx.setStrokeColor(CGColor(srgbRed: Double((rgb >> 16) & 0xFF) / 255,
                           green: Double((rgb >> 8) & 0xFF) / 255,
                           blue: Double(rgb & 0xFF) / 255, alpha: 1))
ctx.setLineWidth(lineW)
ctx.addPath(path)
ctx.strokePath()

guard let out = ctx.makeImage(),
      let dest = CGImageDestinationCreateWithURL(URL(fileURLWithPath: outPath) as CFURL, UTType.png.identifier as CFString, 1, nil) else {
    die("cannot write \(outPath)")
}
CGImageDestinationAddImage(dest, out, nil)
guard CGImageDestinationFinalize(dest) else { die("write failed") }
print("bordered \(w)x\(h) -> \(outPath)")
