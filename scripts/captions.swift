import Foundation
import AVFoundation
import AppKit
import CoreText
import CoreImage
import ImageIO
import UniformTypeIdentifiers

struct Style: Codable {let font_name:String;let base_font_px:Double;let reference_height:Double;let width_scale:Double;let tracking_px:Double;let gradient:[String];let fade_in_seconds:Double;let fade_out_seconds:Double;let safe_margin_px:Double}
struct Caption: Codable {let text:String;let start:Double;let end:Double;let x:Double;let y:Double;let moveToX:Double?;let moveStart:Double?;let moveEnd:Double?;let align:String?}
@main struct RenderCaptions {
 static func main() async throws {
  let a=CommandLine.arguments;guard a.count == 7 else {fatalError("input output captions.json QA-dir report style.json")}
  let style=try JSONDecoder().decode(Style.self,from:Data(contentsOf:URL(fileURLWithPath:a[6])))
  guard style.base_font_px>0 && style.reference_height>0 && style.width_scale>0 && style.fade_in_seconds>0 && style.fade_out_seconds>0 else {fatalError("Invalid style")}
  let source=AVURLAsset(url:URL(fileURLWithPath:a[1]))
  let duration=try await source.load(.duration).seconds
  guard let track=try await source.loadTracks(withMediaType:.video).first else {fatalError("No video")}
  let size=try await track.load(.naturalSize);let w=Int(size.width),h=Int(size.height)
  let transform=try await track.load(.preferredTransform)
  guard transform == .identity else {fatalError("Rotated source not supported")}
  let captions=try JSONDecoder().decode([Caption].self,from:Data(contentsOf:URL(fileURLWithPath:a[3])))
  let space=CGColorSpaceCreateDeviceRGB()
  var overlays:[CIImage]=[]
  var boxes:[[String:Any]]=[]
  var warnings:[String]=[]
  func color(_ hex:String)->CGColor {let raw=hex.trimmingCharacters(in:CharacterSet(charactersIn:"#"));guard let value=UInt32(raw,radix:16),raw.count==6 else {fatalError("Invalid gradient hex")};return CGColor(red:CGFloat((value>>16)&255)/255,green:CGFloat((value>>8)&255)/255,blue:CGFloat(value&255)/255,alpha:1)}
  let frameDirectory=URL(fileURLWithPath:a[4],isDirectory:true);try FileManager.default.createDirectory(at:frameDirectory,withIntermediateDirectories:true)
  for (i,c) in captions.enumerated(){
   let ctx=CGContext(data:nil,width:w,height:h,bitsPerComponent:8,bytesPerRow:w*4,space:space,bitmapInfo:CGImageAlphaInfo.premultipliedLast.rawValue)!
   guard c.start>=0 && c.end>c.start && c.end<=duration+0.12 && c.x>=0 && c.x<=1 && c.y>=0 && c.y<=1 && !c.text.contains("\n") else {fatalError("Invalid caption interval or position")}
   let fs=CGFloat(style.base_font_px)*CGFloat(h)/CGFloat(style.reference_height)
   var fontMatrix=CGAffineTransform(scaleX:style.width_scale,y:1)
   let font=CTFontCreateWithName(style.font_name as CFString,fs,&fontMatrix)
   let attributes:[NSAttributedString.Key:Any]=[NSAttributedString.Key(kCTFontAttributeName as String):font,NSAttributedString.Key(kCTKernAttributeName as String):style.tracking_px*Double(h)/style.reference_height]
   let line=CTLineCreateWithAttributedString(NSAttributedString(string:c.text,attributes:attributes))
   let width=CTLineGetTypographicBounds(line,nil,nil,nil)
   let x=CGFloat(c.x)*CGFloat(w)-(c.align == "left" ? 0 : CGFloat(width)/2)
   let y=CGFloat(c.y)*CGFloat(h)-fs*0.35
   var ascent:CGFloat=0,descent:CGFloat=0,leading:CGFloat=0
   _=CTLineGetTypographicBounds(line,&ascent,&descent,&leading)
   guard x>=0 && x+CGFloat(width)<=CGFloat(w) && y-descent>=0 && y+ascent<=CGFloat(h) else {fatalError("Caption exceeds image bounds: \(c.text)")}
   let margin=style.safe_margin_px*Double(h)/style.reference_height
   if min(Double(x),Double(w)-Double(x)-width,Double(y-descent),Double(h)-Double(y+ascent))<margin {warnings.append("Caption is close to frame edge: \(c.text)")}
   if c.end-c.start-style.fade_in_seconds-style.fade_out_seconds<0.75-0.00001 {warnings.append("Short full-opacity hold: \(c.text)")}
   boxes.append(["text":c.text,"start":c.start,"end":c.end,"left":Double(x),"bottom":Double(y-descent),"width":width,"height":Double(ascent+descent)])
   ctx.textMatrix = .identity;ctx.textPosition=CGPoint(x:x,y:y);ctx.setTextDrawingMode(.clip)
   CTLineDraw(line,ctx)
   guard style.gradient.count==2 else {fatalError("Exactly two gradient colors required")}
   let colors=style.gradient.map(color) as CFArray
   let gradient=CGGradient(colorsSpace:space,colors:colors,locations:[0,1])!
   ctx.drawLinearGradient(gradient,start:CGPoint(x:x,y:y),end:CGPoint(x:x+width,y:y),options:[.drawsBeforeStartLocation,.drawsAfterEndLocation])
   let img=ctx.makeImage()!;overlays.append(CIImage(cgImage:img))
   let png=frameDirectory.appendingPathComponent("overlay_\(i).png")
   let dst=CGImageDestinationCreateWithURL(png as CFURL,UTType.png.identifier as CFString,1,nil)!;CGImageDestinationAddImage(dst,img,nil);CGImageDestinationFinalize(dst)
  }
  let reader=try AVAssetReader(asset:source)
  let output=AVAssetReaderTrackOutput(track:track,outputSettings:[kCVPixelBufferPixelFormatTypeKey as String:kCVPixelFormatType_32BGRA]);output.alwaysCopiesSampleData=false;reader.add(output)
  let destination=URL(fileURLWithPath:a[2]);if FileManager.default.fileExists(atPath:destination.path){try FileManager.default.removeItem(at:destination)}
  let writer=try AVAssetWriter(outputURL:destination,fileType:.mp4)
  let settings:[String:Any]=[AVVideoCodecKey:AVVideoCodecType.h264,AVVideoWidthKey:w,AVVideoHeightKey:h,AVVideoCompressionPropertiesKey:[AVVideoAverageBitRateKey:4500000,AVVideoProfileLevelKey:AVVideoProfileLevelH264HighAutoLevel]]
  let input=AVAssetWriterInput(mediaType:.video,outputSettings:settings);input.expectsMediaDataInRealTime=false
  let adaptor=AVAssetWriterInputPixelBufferAdaptor(assetWriterInput:input,sourcePixelBufferAttributes:[kCVPixelBufferPixelFormatTypeKey as String:kCVPixelFormatType_32BGRA,kCVPixelBufferWidthKey as String:w,kCVPixelBufferHeightKey as String:h,kCVPixelBufferIOSurfacePropertiesKey as String:[:] as [String:Any]])
  writer.add(input);writer.startWriting();writer.startSession(atSourceTime:.zero);reader.startReading()
  let ci=CIContext(options:[.cacheIntermediates:false]);var count=0
  while let sb=output.copyNextSampleBuffer(){
   let pts=CMSampleBufferGetPresentationTimeStamp(sb);if pts.seconds>=duration{break}
   guard let original=CMSampleBufferGetImageBuffer(sb) else {continue}
   var composed=CIImage(cvPixelBuffer:original)
   for (i,c) in captions.enumerated() where pts.seconds>=c.start && pts.seconds<c.end {
    let incoming=min(1.0,max(0.0,(pts.seconds-c.start)/style.fade_in_seconds))
    let outgoing=min(1.0,max(0.0,(c.end-pts.seconds)/style.fade_out_seconds))
    let alpha=min(incoming*incoming*(3-2*incoming),outgoing*outgoing*(3-2*outgoing))
    let overlay=overlays[i].applyingFilter("CIColorMatrix",parameters:["inputAVector":CIVector(x:0,y:0,z:0,w:alpha)])
    composed=overlay.composited(over:composed)
   }
   while !input.isReadyForMoreMediaData{try await Task.sleep(nanoseconds:1000000);if writer.status == .failed{throw writer.error!}}
   var pixel:CVPixelBuffer?;guard CVPixelBufferPoolCreatePixelBuffer(nil,adaptor.pixelBufferPool!,&pixel) == kCVReturnSuccess,let pixel=pixel else {fatalError("No output pixel buffer")}
   ci.render(composed,to:pixel,bounds:CGRect(x:0,y:0,width:w,height:h),colorSpace:space)
   guard adaptor.append(pixel,withPresentationTime:pts) else {throw writer.error!}
   count+=1
  }
  input.markAsFinished();writer.endSession(atSourceTime:CMTime(seconds:duration,preferredTimescale:600));await writer.finishWriting()
  guard writer.status == .completed else {throw writer.error!}
  let final=AVURLAsset(url:destination)
  let gen=AVAssetImageGenerator(asset:final);gen.appliesPreferredTrackTransform=true;gen.maximumSize=CGSize(width:640,height:360)
  gen.requestedTimeToleranceBefore = .zero;gen.requestedTimeToleranceAfter = .zero
  var sampleTimes:[Double]=[0.0]
  for caption in captions {
   let midpoint=(caption.start+caption.end)/2.0
   let beforeFade=caption.end-style.fade_out_seconds-0.02
   let safeTime=min(beforeFade,duration-0.05)
   sampleTimes.append(midpoint)
   sampleTimes.append(max(caption.start,safeTime))
  }
  sampleTimes=Array(Set(sampleTimes)).sorted()
  sampleTimes=sampleTimes.filter { time in time>=0 && time<duration-0.02 }
  for (i,t) in sampleTimes.enumerated(){
   let img=try await gen.image(at:CMTime(seconds:t,preferredTimescale:600)).image
   let png=frameDirectory.appendingPathComponent(String(format:"final_%02d_%.1fs.png",i,t));let dst=CGImageDestinationCreateWithURL(png as CFURL,UTType.png.identifier as CFString,1,nil)!;CGImageDestinationAddImage(dst,img,nil);CGImageDestinationFinalize(dst)
  }
  let report:[String:Any]=["durationSeconds":try await final.load(.duration).seconds,"width":w,"height":h,"framesWritten":count,"audioTracks":try await final.loadTracks(withMediaType:.audio).count,"titleFile":destination.path,"captionBounds":boxes,"warnings":warnings,"visual_qa":"pending","fontName":style.font_name,"fontPixels":style.base_font_px*Double(h)/style.reference_height,"fadeInSeconds":style.fade_in_seconds,"fadeOutSeconds":style.fade_out_seconds,"backgroundReplaced":false,"movementAdded":false]
  let data=try JSONSerialization.data(withJSONObject:report,options:[.prettyPrinted,.sortedKeys]);try data.write(to:URL(fileURLWithPath:a[5]));print(String(data:data,encoding:.utf8)!)
 }
}
