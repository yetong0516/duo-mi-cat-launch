import Foundation
import AVFoundation
import CryptoKit

@main struct Verify {
 static func hashes(_ path:String) async throws->[String] {
  let asset=AVURLAsset(url:URL(fileURLWithPath:path))
  let reader=try AVAssetReader(asset:asset)
  let track=try await asset.loadTracks(withMediaType:.video).first!
  let output=AVAssetReaderTrackOutput(track:track,outputSettings:nil)
  reader.add(output);reader.startReading();var result:[String]=[]
  while let sample=output.copyNextSampleBuffer() {
   guard let buffer=CMSampleBufferGetDataBuffer(sample) else {continue}
   let length=CMBlockBufferGetDataLength(buffer);var bytes=Data(count:length)
   _ = bytes.withUnsafeMutableBytes{ p in CMBlockBufferCopyDataBytes(buffer,atOffset:0,dataLength:length,destination:p.baseAddress!) }
   result.append(SHA256.hash(data:bytes).map{String(format:"%02x",$0)}.joined())
  }
  guard reader.status == .completed else {throw reader.error!}
  guard !result.isEmpty else {fatalError("No encoded video frames")}
  return result
 }
 static func main() async throws {
  let a=CommandLine.arguments;guard a.count==5 else {fatalError("Wrong argument count")}
  let first=try await hashes(a[1]),second=try await hashes(a[2]),final=try await hashes(a[3])
  guard first+second == final else {fatalError("Encoded source video differs from output")}
  let report:[String:Any]=["aFrames":first.count,"bFrames":second.count,"outputFrames":final.count,"allEncodedVideoFramesIdentical":true,"backgroundAndPicturePreserved":true,"passed":true]
  let data=try JSONSerialization.data(withJSONObject:report,options:[.prettyPrinted,.sortedKeys]);try data.write(to:URL(fileURLWithPath:a[4]));print(String(data:data,encoding:.utf8)!)
 }
}
