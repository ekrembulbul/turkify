// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "Turkify",
    platforms: [
        .macOS(.v13)  // MenuBarExtra macOS 13+ gerektirir
    ],
    targets: [
        .executableTarget(
            name: "Turkify",
            path: "Sources/Turkify"
        )
    ]
)
