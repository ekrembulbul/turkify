import Carbon.HIToolbox

/// Global kısayol — Carbon `RegisterEventHotKey` ile (Input Monitoring gerektirmez,
/// sistem genelinde çalışır). Tek bir global event handler kurulur; tüm kısayollar
/// `id` ile statik bir kayıt defterinden eşleştirilir.
///
/// ⚠️ Bu dosya, projedeki en "düşük seviye" (C köprülü) parça; ilk Xcode
/// derlemesinde en olası iterasyon noktası burasıdır.
final class HotKey {
    private var hotKeyRef: EventHotKeyRef?
    private let identifier: UInt32

    private static let signature: OSType = 0x544B4659  // 'TKFY'
    // Registry YALNIZCA eylem closure'unu tutar, HotKey nesnesini DEĞİL. Nesneyi
    // tutsaydı statik sözlük onu güçlü referansla canlı tutar, sahip (AppState)
    // referansı bıraksa bile `deinit` hiç çalışmaz → Carbon kısayolu
    // `UnregisterEventHotKey` edilmez. Sonuç: kayıt sırasında eski kısayol hâlâ
    // tetiklenir ve her yeniden kayıtta kısayollar birikir (sızıntı).
    private static var registry: [UInt32: () -> Void] = [:]
    private static var counter: UInt32 = 0
    private static var handlerInstalled = false

    /// - Parameters:
    ///   - keyCode: sanal tuş kodu (bkz. `keyCode(for:)`)
    ///   - modifiers: Carbon modifier maskesi (bkz. `carbonModifiers(from:)`)
    init?(keyCode: UInt32, modifiers: UInt32, action: @escaping () -> Void) {
        HotKey.counter += 1
        self.identifier = HotKey.counter
        HotKey.installHandlerIfNeeded()

        let hotKeyID = EventHotKeyID(signature: HotKey.signature, id: identifier)
        let status = RegisterEventHotKey(
            keyCode, modifiers, hotKeyID, GetEventDispatcherTarget(), 0, &hotKeyRef
        )
        if status != noErr {
            return nil
        }
        HotKey.registry[identifier] = action
    }

    deinit {
        if let ref = hotKeyRef { UnregisterEventHotKey(ref) }
        HotKey.registry[identifier] = nil
    }

    private static func installHandlerIfNeeded() {
        guard !handlerInstalled else { return }
        handlerInstalled = true
        var spec = EventTypeSpec(
            eventClass: OSType(kEventClassKeyboard),
            eventKind: UInt32(kEventHotKeyPressed)
        )
        // Capture'sız closure → C fonksiyon işaretçisine dönüşebilir.
        InstallEventHandler(
            GetEventDispatcherTarget(),
            { (_, event, _) -> OSStatus in
                guard let event else { return noErr }
                var hkID = EventHotKeyID()
                GetEventParameter(
                    event, EventParamName(kEventParamDirectObject),
                    EventParamType(typeEventHotKeyID), nil,
                    MemoryLayout<EventHotKeyID>.size, nil, &hkID
                )
                if let action = HotKey.registry[hkID.id] {
                    DispatchQueue.main.async { action() }
                }
                return noErr
            },
            1, &spec, nil, nil
        )
    }

    // MARK: - Config eşlemeleri

    /// Config `mods` adlarını Carbon modifier maskesine çevirir.
    static func carbonModifiers(from mods: [String]) -> UInt32 {
        var mask: UInt32 = 0
        for mod in mods {
            switch mod.lowercased() {
            case "ctrl", "control": mask |= UInt32(controlKey)
            case "alt", "opt", "option": mask |= UInt32(optionKey)
            case "cmd", "command", "win", "windows", "super": mask |= UInt32(cmdKey)
            case "shift": mask |= UInt32(shiftKey)
            default: break
            }
        }
        return mask
    }

    /// Tek harf/rakam → US-ANSI sanal tuş kodu. Bilinmiyorsa nil.
    static func keyCode(for key: String) -> UInt32? {
        let map: [String: UInt32] = [
            "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7,
            "c": 8, "v": 9, "b": 11, "q": 12, "w": 13, "e": 14, "r": 15, "y": 16,
            "t": 17, "1": 18, "2": 19, "3": 20, "4": 21, "6": 22, "5": 23, "9": 25,
            "7": 26, "8": 28, "0": 29, "o": 31, "u": 32, "i": 34, "p": 35,
            "l": 37, "j": 38, "k": 40, "n": 45, "m": 46,
        ]
        return map[key.lowercased()]
    }
}
