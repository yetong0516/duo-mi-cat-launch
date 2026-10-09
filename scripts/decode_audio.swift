import Foundation
import AVFoundation
import CoreMedia
@main struct DecodePCM {
 static func main() async throws {
  let a=CommandLine.arguments;guard a.count==3 else {fatalError("Wrong argument count")};let source=AVURLAsset(url:URL(fileURLWithPath:a[1]));let track=try await source.loadTracks(withMediaType:.audio).first!;let reader=try AVAssetReader(asset:source)
  let settings:[String:Any]=[AVFormatIDKey:kAudioFormatLinearPCM,AVLinearPCMBitDepthKey:16,AVLinearPCMIsFloatKey:false,AVLinearPCMIsNonInterleaved:false,AVLinearPCMIsBigEndianKey:false,AVSampleRateKey:44100,AVNumberOfChannelsKey:2]
  let output=AVAssetReaderTrackOutput(track:track,outputSettings:settings);reader.add(output);reader.startReading();var data=Data()
  while let sb=output.copyNextSampleBuffer(){if let b=CMSampleBufferGetDataBuffer(sb){let len=CMBlockBufferGetDataLength(b);var chunk=Data(count:len);chunk.withUnsafeMutableBytes{p in CMBlockBufferCopyDataBytes(b,atOffset:0,dataLength:len,destination:p.baseAddress!)};data.append(chunk)}}
  guard reader.status == .completed else {throw reader.error!};try data.write(to:URL(fileURLWithPath:a[2]));print("decoded stereo PCM16",data.count/4,"frames at 44100Hz")
 }
}
