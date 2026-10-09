import Foundation
import AVFoundation

@main struct Concat {
 static func main() async throws {
  let a=CommandLine.arguments;guard a.count==6 || (a.count==7 && a[6]=="mixed") else {fatalError("Wrong argument count")}
  let mixed=a.count==7
  let composition=AVMutableComposition()
  let target=composition.addMutableTrack(withMediaType:.video,preferredTrackID:kCMPersistentTrackID_Invalid)!
  var cursor=CMTime.zero
  var segments:[[String:Any]]=[]
  for path in [a[1],a[2]] {
   let asset=AVURLAsset(url:URL(fileURLWithPath:path))
   guard let track=try await asset.loadTracks(withMediaType:.video).first else {fatalError("No video")}
   let range=try await track.load(.timeRange)
   try target.insertTimeRange(range,of:track,at:cursor)
   if cursor == .zero {target.preferredTransform=try await track.load(.preferredTransform)}
   segments.append(["source":path,"sourceStartSeconds":range.start.seconds,"sourceDurationSeconds":range.duration.seconds,"outputStartSeconds":cursor.seconds])
   cursor=CMTimeAdd(cursor,range.duration)
  }
  var musicDuration=CMTime.zero
  if a[3] != "-" {
   let music=AVURLAsset(url:URL(fileURLWithPath:a[3]))
   guard let musicTrack=try await music.loadTracks(withMediaType:.audio).first else {fatalError("No music track")}
   let musicRange=try await musicTrack.load(.timeRange)
   musicDuration=CMTimeMinimum(cursor,musicRange.duration)
   let audio=composition.addMutableTrack(withMediaType:.audio,preferredTrackID:kCMPersistentTrackID_Invalid)!
   try audio.insertTimeRange(CMTimeRange(start:musicRange.start,duration:musicDuration),of:musicTrack,at:.zero)
  }
  let out=URL(fileURLWithPath:a[4])
  if FileManager.default.fileExists(atPath:out.path){try FileManager.default.removeItem(at:out)}
  let exporter=AVAssetExportSession(asset:composition,presetName:AVAssetExportPresetPassthrough)!
  exporter.shouldOptimizeForNetworkUse=true
  try await exporter.export(to:out,as:.mp4)
  let final=AVURLAsset(url:out),video=try await final.loadTracks(withMediaType:.video).first!
  let size=try await video.load(.naturalSize)
  var report:[String:Any]=["file":out.path,"durationSeconds":try await final.load(.duration).seconds,"width":size.width,"height":size.height,"fps":try await video.load(.nominalFrameRate),"audioTracks":try await final.loadTracks(withMediaType:.audio).count,"segments":segments,"audioSource":a[3],"audioDurationSeconds":musicDuration.seconds,"videoExport":"Passthrough: original encoded video copied without filters or re-encoding","voiceoverAdded":mixed,"captionsAdded":false,"backgroundChanged":false,"speedChanged":false,"cropOrResizeApplied":false,"audio":mixed ? "One pre-mixed narration/music AAC track; original clip audio omitted" : "Only the specified background music, at original volume and timing; original clip audio omitted"]
  if !mixed {report["musicSource"]=a[3];report["musicDurationSeconds"]=musicDuration.seconds}
  let data=try JSONSerialization.data(withJSONObject:report,options:[.prettyPrinted,.sortedKeys]);try data.write(to:URL(fileURLWithPath:a[5]));print(String(data:data,encoding:.utf8)!)
 }
}
