import Foundation
import AVFoundation
@main struct AudioAAC {
 static func main() async throws {
  let a=CommandLine.arguments;guard a.count==3 else {fatalError("input output.m4a")}
  let asset=AVURLAsset(url:URL(fileURLWithPath:a[1]))
  guard let audio=try await asset.loadTracks(withMediaType:.audio).first else {fatalError("No audio")}
  let composition=AVMutableComposition()
  let destinationTrack=composition.addMutableTrack(withMediaType:.audio,preferredTrackID:kCMPersistentTrackID_Invalid)!
  try destinationTrack.insertTimeRange(try await audio.load(.timeRange),of:audio,at:.zero)
  let url=URL(fileURLWithPath:a[2]);if FileManager.default.fileExists(atPath:url.path){try FileManager.default.removeItem(at:url)}
  let exporter=AVAssetExportSession(asset:composition,presetName:AVAssetExportPresetAppleM4A)!
  try await exporter.export(to:url,as:.m4a)
  print("Converted only the music track to AAC")
 }
}
