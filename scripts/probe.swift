import Foundation
import AVFoundation
import ImageIO
import UniformTypeIdentifiers

@main struct Probe {
 static func main() async throws {
  let a=CommandLine.arguments
  guard a.count==3 || a.count==5 else {fatalError("input report.json [frames-dir step]")}
  let asset=AVURLAsset(url:URL(fileURLWithPath:a[1]))
  var report:[String:Any]=["file":a[1],"durationSeconds":try await asset.load(.duration).seconds]
  let videos=try await asset.loadTracks(withMediaType:.video),audios=try await asset.loadTracks(withMediaType:.audio)
  report["audioTracks"]=audios.count;report["videoTracks"]=videos.count
  if let audio=audios.first {
   let range=try await audio.load(.timeRange)
   report["audioStartSeconds"]=range.start.seconds;report["audioDurationSeconds"]=range.duration.seconds
   let formats=try await audio.load(.formatDescriptions)
   if let format=formats.first {report["audioFormatID"]=CMFormatDescriptionGetMediaSubType(format)}
  }
  if let video=videos.first {
   let natural=try await video.load(.naturalSize),transform=try await video.load(.preferredTransform),range=try await video.load(.timeRange)
   let display=natural.applying(transform),fps=try await video.load(.nominalFrameRate)
   report["width"]=abs(display.width);report["height"]=abs(display.height);report["naturalWidth"]=natural.width;report["naturalHeight"]=natural.height
   report["identityTransform"]=transform == .identity;report["fps"]=fps;report["videoStartSeconds"]=range.start.seconds;report["videoDurationSeconds"]=range.duration.seconds
   let reader=try AVAssetReader(asset:asset)
   let output=AVAssetReaderTrackOutput(track:video,outputSettings:[kCVPixelBufferPixelFormatTypeKey as String:kCVPixelFormatType_32BGRA])
   output.alwaysCopiesSampleData=false;reader.add(output);reader.startReading()
   var count=0,last:Double=range.start.seconds,previous:[Double]?=nil,cuts:[[String:Double]]=[]
   while let sample=output.copyNextSampleBuffer() {
    guard let pixel=CMSampleBufferGetImageBuffer(sample) else {continue}
    last=CMSampleBufferGetPresentationTimeStamp(sample).seconds;count+=1
    if a.count==5 {
     CVPixelBufferLockBaseAddress(pixel,.readOnly)
     let bytes=CVPixelBufferGetBaseAddress(pixel)!.assumingMemoryBound(to:UInt8.self)
     let w=CVPixelBufferGetWidth(pixel),h=CVPixelBufferGetHeight(pixel),stride=CVPixelBufferGetBytesPerRow(pixel)
     var values:[Double]=[]
     for y in 0..<18 {for x in 0..<32 {let p=y*h/18*stride+x*w/32*4;values.append((0.0722*Double(bytes[p])+0.7152*Double(bytes[p+1])+0.2126*Double(bytes[p+2]))/255)}}
     CVPixelBufferUnlockBaseAddress(pixel,.readOnly)
     if let old=previous {let difference=zip(values,old).reduce(0.0){$0+abs($1.0-$1.1)}/Double(values.count);if difference>0.08 {cuts.append(["seconds":last,"difference":difference])}}
     previous=values
    }
   }
   guard reader.status == .completed else {throw reader.error!}
   report["frames"]=count;report["lastFrameSeconds"]=last
   if a.count==5 {
    let directory=URL(fileURLWithPath:a[3],isDirectory:true);try FileManager.default.createDirectory(at:directory,withIntermediateDirectories:true)
    guard let step=Double(a[4]),step>0 else {fatalError("Invalid step")}
    let generator=AVAssetImageGenerator(asset:asset);generator.appliesPreferredTrackTransform=true;generator.maximumSize=CGSize(width:960,height:540)
    generator.requestedTimeToleranceBefore = .zero;generator.requestedTimeToleranceAfter = .zero
    var times=Array(stride(from:range.start.seconds,to:last,by:step));times.append(last)
    var frames:[[String:Any]]=[]
    for (i,time) in times.enumerated() {
     let result=try await generator.image(at:CMTime(seconds:time+0.00001,preferredTimescale:60000))
     let url=directory.appendingPathComponent(String(format:"%03d_%.4fs.png",i,time))
     let destination=CGImageDestinationCreateWithURL(url as CFURL,UTType.png.identifier as CFString,1,nil)!
     CGImageDestinationAddImage(destination,result.image,nil);guard CGImageDestinationFinalize(destination) else {fatalError("Frame write failed")}
     frames.append(["requestedSeconds":time,"actualSeconds":result.actualTime.seconds,"file":url.path])
    }
    report["framesExtracted"]=frames;report["candidateCuts"]=cuts
   }
  }
  let data=try JSONSerialization.data(withJSONObject:report,options:[.prettyPrinted,.sortedKeys]);try data.write(to:URL(fileURLWithPath:a[2]));print(String(data:data,encoding:.utf8)!)
 }
}
