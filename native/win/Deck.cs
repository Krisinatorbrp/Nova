using System.Diagnostics;

namespace WinDock;

/// <summary>
/// Stream Deck buttons: keyboard shortcuts for the foreground window and
/// websites in the default browser. Inputs were validated by the host already;
/// they are checked again here against the same allowlist before Win32 sees them.
/// </summary>
internal static class Deck
{
    private const uint KeyUp = 0x0002, ExtendedKey = 0x0001;
    private const uint MapVkToScan = 0;

    [System.Runtime.InteropServices.DllImport("user32.dll")]
    private static extern uint MapVirtualKey(uint code, uint mapType);

    private static readonly (string Name, ushort Vk)[] Modifiers =
    {
        ("ctrl", 0xA2), ("alt", 0xA4), ("shift", 0xA0), ("win", 0x5B),
    };

    private static readonly Dictionary<string, ushort> Named = new()
    {
        ["enter"] = 0x0D, ["tab"] = 0x09, ["escape"] = 0x1B, ["space"] = 0x20, ["backspace"] = 0x08,
        ["delete"] = 0x2E, ["insert"] = 0x2D, ["home"] = 0x24, ["end"] = 0x23, ["pageup"] = 0x21, ["pagedown"] = 0x22,
        ["left"] = 0x25, ["up"] = 0x26, ["right"] = 0x27, ["down"] = 0x28, ["printscreen"] = 0x2C, ["pause"] = 0x13,
        ["minus"] = 0xBD, ["equals"] = 0xBB, ["comma"] = 0xBC, ["period"] = 0xBE, ["slash"] = 0xBF,
        ["semicolon"] = 0xBA, ["quote"] = 0xDE, ["bracketleft"] = 0xDB, ["bracketright"] = 0xDD,
        ["backslash"] = 0xDC, ["backquote"] = 0xC0,
    };

    /// <summary>Keys Windows treats as extended (arrows, navigation block, Win).</summary>
    private static readonly HashSet<ushort> Extended = new() { 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E, 0x5B };

    internal static ushort? KeyCode(string key)
    {
        if (key.Length == 1 && key[0] is >= 'a' and <= 'z') return (ushort)(0x41 + key[0] - 'a');
        if (key.Length == 1 && key[0] is >= '0' and <= '9') return (ushort)(0x30 + key[0] - '0');
        if (key.Length is 2 or 3 && key[0] == 'f' && int.TryParse(key.AsSpan(1), out var f) && f is >= 1 and <= 24 && key[1] != '0')
            return (ushort)(0x70 + f - 1);
        if (key.Length == 7 && key.StartsWith("numpad", StringComparison.Ordinal) && key[6] is >= '0' and <= '9')
            return (ushort)(0x60 + key[6] - '0');
        return Named.TryGetValue(key, out var vk) ? vk : null;
    }

    /// <summary>
    /// Press modifiers in order, tap the key, release in reverse, all in one
    /// SendInput batch so no other input can land between them. Null when the
    /// combination is not canonical (e.g. "shift+ctrl+m" or an unknown key).
    /// </summary>
    internal static Touchpad.Input[]? HotkeyInputs(string combo, Func<ushort, ushort>? scan = null)
    {
        if (string.IsNullOrEmpty(combo) || combo.Length > 60) return null;
        var parts = combo.Split('+');
        if (parts.Length is < 1 or > 5) return null;
        var mods = new List<ushort>();
        var next = 0;
        for (var i = 0; i < parts.Length - 1; i++)
        {
            var index = Array.FindIndex(Modifiers, m => m.Name == parts[i]);
            if (index < next) return null; // unknown, repeated or out of canonical order
            mods.Add(Modifiers[index].Vk);
            next = index + 1;
        }
        if (KeyCode(parts[^1]) is not ushort key) return null;
        scan ??= vk => (ushort)MapVirtualKey(vk, MapVkToScan);
        Touchpad.Input Make(ushort vk, bool up) => new()
        {
            type = 1,
            value = new Touchpad.InputUnion
            {
                keyboard = new Touchpad.KeyboardInput
                {
                    key = vk,
                    scan = scan(vk),
                    flags = (up ? KeyUp : 0) | (Extended.Contains(vk) ? ExtendedKey : 0),
                },
            },
        };
        var inputs = new List<Touchpad.Input>();
        foreach (var vk in mods) inputs.Add(Make(vk, false));
        inputs.Add(Make(key, false));
        inputs.Add(Make(key, true));
        for (var i = mods.Count - 1; i >= 0; i--) inputs.Add(Make(mods[i], true));
        return inputs.ToArray();
    }

    internal static int Hotkey(string[] args)
    {
        if (args.Length != 2) return Fail("usage: hotkey <combo>", 1);
        var inputs = HotkeyInputs(args[1]);
        if (inputs is null) return Fail("hotkey: unsupported combination", 1);
        return Touchpad.Send(inputs) == inputs.Length ? 0 : Fail("hotkey: input was blocked", 2);
    }

    /// <summary>Absolute http(s) URL without credentials or whitespace, else null.</summary>
    internal static Uri? CheckedUrl(string text)
    {
        if (string.IsNullOrEmpty(text) || text.Length > 500 || text.Any(c => char.IsWhiteSpace(c) || char.IsControl(c))) return null;
        if (!Uri.TryCreate(text, UriKind.Absolute, out var uri)) return null;
        if (uri.Scheme != Uri.UriSchemeHttp && uri.Scheme != Uri.UriSchemeHttps) return null;
        if (!string.IsNullOrEmpty(uri.UserInfo) || string.IsNullOrEmpty(uri.Host)) return null;
        return uri;
    }

    internal static int OpenUrl(string[] args)
    {
        if (args.Length != 2) return Fail("usage: open-url <http(s) url>", 1);
        var uri = CheckedUrl(args[1]);
        if (uri is null) return Fail("open-url: only http and https addresses are allowed", 1);
        // The shell hands an http(s) URI to the user's default browser.
        using var process = Process.Start(new ProcessStartInfo(uri.AbsoluteUri) { UseShellExecute = true });
        return 0;
    }

    private static int Fail(string message, int code)
    {
        Console.Error.WriteLine(message);
        return code;
    }
}
