import Foundation
import AVFoundation

struct AudioInput: Decodable { let file: String; let start: Double; let duration: Double; let gain: Float }
struct Window: Decodable { let start: Double; let end: Double }
struct MixConfig: Decodable {
 let durationSeconds: Double
 let music: String?
 let musicGain: Float
 let musicDuckGain: Float
 let duckFadeSeconds: Double
 let windows: [Window]
 let inputs: [AudioInput]
}

@main struct MixAudio {
 static func time(_ seconds: Double) -> CMTime { CMTime(seconds: seconds, preferredTimescale: 44100) }
 static func main() async throws {
  let args = CommandLine.arguments
  guard args.count == 4 else { throw NSError(domain: "MixAudio", code: 1, userInfo: [NSLocalizedDescriptionKey: "config.json output.m4a report.json"]) }
  let config = try JSONDecoder().decode(MixConfig.self, from: Data(contentsOf: URL(fileURLWithPath: args[1])))
  let composition = AVMutableComposition()
  var parameters: [AVMutableAudioMixInputParameters] = []
  var inserted: [[String: Any]] = []
  func add(_ file: String, at start: Double, duration: Double, gain: Float) async throws -> AVMutableAudioMixInputParameters {
   let asset = AVURLAsset(url: URL(fileURLWithPath: file))
   guard let source = try await asset.loadTracks(withMediaType: .audio).first else { throw NSError(domain: "MixAudio", code: 2, userInfo: [NSLocalizedDescriptionKey: "No audio in \(file)"]) }
   let sourceRange = try await source.load(.timeRange)
   let length = min(duration, sourceRange.duration.seconds, config.durationSeconds - start)
   guard length > 0, length.isFinite else { throw NSError(domain: "MixAudio", code: 3, userInfo: [NSLocalizedDescriptionKey: "Invalid audio range in \(file)"]) }
   let track = composition.addMutableTrack(withMediaType: .audio, preferredTrackID: kCMPersistentTrackID_Invalid)!
   try track.insertTimeRange(CMTimeRange(start: sourceRange.start, duration: time(length)), of: source, at: time(start))
   let parameter = AVMutableAudioMixInputParameters(track: track)
   parameter.setVolume(gain, at: .zero)
   parameters.append(parameter)
   inserted.append(["file": file, "start": start, "duration": length, "gain": gain])
   return parameter
  }
  if let music = config.music {
   let parameter = try await add(music, at: 0, duration: config.durationSeconds, gain: config.musicGain)
   var previousEnd = 0.0
   for (index, window) in config.windows.enumerated() {
    let before = min(config.duckFadeSeconds, max(0, (window.start - previousEnd) / 2))
    let nextStart = index + 1 < config.windows.count ? config.windows[index + 1].start : config.durationSeconds
    let after = min(config.duckFadeSeconds, max(0, (nextStart - window.end) / 2))
    if before > 0 {
     parameter.setVolumeRamp(fromStartVolume: config.musicGain, toEndVolume: config.musicDuckGain, timeRange: CMTimeRange(start: time(window.start - before), duration: time(before)))
    } else { parameter.setVolume(config.musicDuckGain, at: time(window.start)) }
    parameter.setVolume(config.musicDuckGain, at: time(window.end))
    if after > 0 {
     parameter.setVolumeRamp(fromStartVolume: config.musicDuckGain, toEndVolume: config.musicGain, timeRange: CMTimeRange(start: time(window.end), duration: time(after)))
    } else if window.end < nextStart { parameter.setVolume(config.musicGain, at: time(window.end)) }
    previousEnd = window.end
   }
  }
  for input in config.inputs { _ = try await add(input.file, at: input.start, duration: input.duration, gain: input.gain) }
  let mix = AVMutableAudioMix(); mix.inputParameters = parameters
  let output = URL(fileURLWithPath: args[2])
  if FileManager.default.fileExists(atPath: output.path) { try FileManager.default.removeItem(at: output) }
  guard let exporter = AVAssetExportSession(asset: composition, presetName: AVAssetExportPresetAppleM4A) else { throw NSError(domain: "MixAudio", code: 4) }
  exporter.audioMix = mix
  exporter.timeRange = CMTimeRange(start: .zero, duration: time(config.durationSeconds))
  try await exporter.export(to: output, as: .m4a)
  let final = AVURLAsset(url: output)
  let report: [String: Any] = ["file": output.path, "durationSeconds": try await final.load(.duration).seconds, "audioTracks": try await final.loadTracks(withMediaType: .audio).count, "musicGain": config.musicGain, "musicDuckGain": config.musicDuckGain, "duckFadeSeconds": config.duckFadeSeconds, "speechWindows": config.windows.map { ["start": $0.start, "end": $0.end] }, "inputs": inserted, "export": "AAC audio mix; one output audio track"]
  let data = try JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys])
  try data.write(to: URL(fileURLWithPath: args[3]))
  print(String(data: data, encoding: .utf8)!)
 }
}
