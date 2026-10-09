import Foundation
import AVFoundation
import ImageIO
import UniformTypeIdentifiers
@main struct Extract {
 static func main() async throws {
  let a=CommandLine.arguments;guard a.count==4 else {fatalError("Wrong argument count")}
  let asset=AVURLAsset(url:URL(fileURLWithPath:a[1]))
  let gen=AVAssetImageGenerator(asset:asset)
  gen.appliesPreferredTrackTransform=true
  gen.requestedTimeToleranceBefore = .zero
  gen.requestedTimeToleranceAfter = .zero
  let r=try await gen.image(at:CMTime(seconds:Double(a[2])!,preferredTimescale:60000))
  let url=URL(fileURLWithPath:a[3])
  let dest=CGImageDestinationCreateWithURL(url as CFURL,UTType.png.identifier as CFString,1,nil)!
  CGImageDestinationAddImage(dest,r.image,nil)
  guard CGImageDestinationFinalize(dest) else {fatalError("Write failed")}
  print("Actual frame time: \(r.actualTime.seconds); \(r.image.width)x\(r.image.height)")
 }
}
