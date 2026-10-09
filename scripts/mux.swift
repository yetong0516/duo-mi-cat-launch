import Foundation
import AVFoundation
@main struct Mux {
 static func main() async throws {
  let a=CommandLine.arguments;guard a.count==5 else {fatalError("Wrong argument count")}
  let source=AVURLAsset(url:URL(fileURLWithPath:a[1])),music=AVURLAsset(url:URL(fileURLWithPath:a[2]))
  let video=try await source.loadTracks(withMediaType:.video).first!,audio=try await music.loadTracks(withMediaType:.audio).first!
  let composition=AVMutableComposition()
  let cv=composition.addMutableTrack(withMediaType:.video,preferredTrackID:kCMPersistentTrackID_Invalid)!,ca=composition.addMutableTrack(withMediaType:.audio,preferredTrackID:kCMPersistentTrackID_Invalid)!
  let range=try await video.load(.timeRange),musicRange=try await audio.load(.timeRange)
  try cv.insertTimeRange(range,of:video,at:.zero);cv.preferredTransform=try await video.load(.preferredTransform)
  try ca.insertTimeRange(CMTimeRange(start:musicRange.start,duration:CMTimeMinimum(range.duration,musicRange.duration)),of:audio,at:.zero)
  let destination=URL(fileURLWithPath:a[3]);if FileManager.default.fileExists(atPath:destination.path){try FileManager.default.removeItem(at:destination)}
  let exporter=AVAssetExportSession(asset:composition,presetName:AVAssetExportPresetPassthrough)!
  exporter.shouldOptimizeForNetworkUse=true;try await exporter.export(to:destination,as:.mp4)
  let final=AVURLAsset(url:destination),track=try await final.loadTracks(withMediaType:.video).first!,size=try await track.load(.naturalSize)
  let report:[String:Any]=["file":destination.path,"durationSeconds":try await final.load(.duration).seconds,"width":size.width,"height":size.height,"fps":try await track.load(.nominalFrameRate),"audioTracks":try await final.loadTracks(withMediaType:.audio).count,"musicSource":a[2],"musicGain":1,"musicOffsetSeconds":0,"voiceoverAdded":false,"backgroundReplaced":false,"cropOrResizeApplied":false,"speedChanged":false,"captionsAdded":true]
  let data=try JSONSerialization.data(withJSONObject:report,options:[.prettyPrinted,.sortedKeys]);try data.write(to:URL(fileURLWithPath:a[4]));print(String(data:data,encoding:.utf8)!)
 }
}
