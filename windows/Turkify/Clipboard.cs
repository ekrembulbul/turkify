using System.Runtime.InteropServices;
using System.Windows.Threading;
using WpfClipboard = System.Windows.Clipboard;

namespace Turkify;

/// Pano okuma/yazma + tuş simülasyonu (Ctrl+C / Ctrl+V). Pano erişimi STA
/// thread'inde olmalıdır; çağrılar UI <see cref="Dispatcher"/> üzerinden yürütülür.
/// (macOS Corrector.swift içindeki Clipboard enum'unun karşılığı.)
public static class ClipboardBridge
{
    private const int RetryCount = 5;
    private const int RetryDelayMs = 30;

    private const int InputKeyboard = 1;
    private const uint KeyEventKeyUp = 0x0002;
    private const ushort VkControl = 0x11;
    private const ushort VkC = 0x43;
    private const ushort VkV = 0x56;

    /// Panodaki metni döner; metin yoksa null. (Pano kilitliyse birkaç kez dener.)
    public static string? Read(Dispatcher dispatcher) =>
        dispatcher.Invoke(() =>
        {
            for (int attempt = 0; attempt < RetryCount; attempt++)
            {
                try
                {
                    return WpfClipboard.ContainsText() ? WpfClipboard.GetText() : null;
                }
                catch (COMException)
                {
                    Thread.Sleep(RetryDelayMs);
                }
            }

            return null;
        });

    public static void Write(Dispatcher dispatcher, string text) =>
        dispatcher.Invoke(() =>
        {
            for (int attempt = 0; attempt < RetryCount; attempt++)
            {
                try
                {
                    WpfClipboard.SetText(text);
                    return;
                }
                catch (COMException)
                {
                    Thread.Sleep(RetryDelayMs);
                }
            }
        });

    public static void SendCopy(Dispatcher dispatcher) => SendCtrl(dispatcher, VkC);

    public static void SendPaste(Dispatcher dispatcher) => SendCtrl(dispatcher, VkV);

    /// Ctrl + <paramref name="key"/> kombinasyonunu aktif uygulamaya gönderir
    /// (Ctrl↓, key↓, key↑, Ctrl↑).
    private static void SendCtrl(Dispatcher dispatcher, ushort key) =>
        dispatcher.Invoke(() =>
        {
            INPUT[] inputs =
            [
                KeyDown(VkControl),
                KeyDown(key),
                KeyUp(key),
                KeyUp(VkControl),
            ];
            SendInput((uint)inputs.Length, inputs, Marshal.SizeOf<INPUT>());
        });

    private static INPUT KeyDown(ushort vk) => MakeInput(vk, 0);

    private static INPUT KeyUp(ushort vk) => MakeInput(vk, KeyEventKeyUp);

    private static INPUT MakeInput(ushort vk, uint flags) => new()
    {
        Type = InputKeyboard,
        Data = new InputUnion
        {
            Keyboard = new KEYBDINPUT
            {
                Vk = vk,
                Scan = 0,
                Flags = flags,
                Time = 0,
                ExtraInfo = IntPtr.Zero,
            },
        },
    };

    [DllImport("user32.dll", SetLastError = true)]
    private static extern uint SendInput(uint nInputs, INPUT[] pInputs, int cbSize);

    [StructLayout(LayoutKind.Sequential)]
    private struct INPUT
    {
        public int Type;
        public InputUnion Data;
    }

    // Union, en büyük üyeye (MOUSEINPUT) göre boyutlanmalı; aksi halde
    // Marshal.SizeOf<INPUT>() Windows'un beklediği boyuttan küçük olur ve SendInput
    // sessizce başarısız olur (x64'te INPUT = 40 bayt).
    [StructLayout(LayoutKind.Explicit)]
    private struct InputUnion
    {
        [FieldOffset(0)]
        public MOUSEINPUT Mouse;

        [FieldOffset(0)]
        public KEYBDINPUT Keyboard;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct MOUSEINPUT
    {
        public int Dx;
        public int Dy;
        public uint MouseData;
        public uint Flags;
        public uint Time;
        public IntPtr ExtraInfo;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct KEYBDINPUT
    {
        public ushort Vk;
        public ushort Scan;
        public uint Flags;
        public uint Time;
        public IntPtr ExtraInfo;
    }
}
