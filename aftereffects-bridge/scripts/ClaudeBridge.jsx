/*  Claude Bridge for After Effects
    --------------------------------
    Lets Claude (Cowork) drive After Effects without an MCP server.
    While this panel is open it checks  <bridge folder>\inbox  every second,
    runs any .jsx file it finds there (one undo step each, named "Claude: <file>"),
    writes the result to  outbox\<file>.json  and moves the script to  done\.

    Signed scripts only: send.sh signs each script with the key in  ~\.claude\ae-bridge.key
    (it creates the key on first use). Anything unsigned, edited after signing, older than an
    hour or already run is refused and moved to  rejected\, so nothing else that can write into
    inbox (another program, a synced folder) can run code here.

    Bridge folder: the one set with  ClaudeBridge.useFolder(path)  from a bridge script (ask
    Claude to switch it; remembered in AE's settings). Until then: the folder this file sits in, or
    Documents\ClaudeBridge  when this file is installed in one of AE's Scripts folders (AE lists
    every script there) or its folder is read-only.

    Install:  File > Scripts > Install ScriptUI Panel...  > pick this file, restart AE, open
              Window > ClaudeBridge.jsx and dock it - it then opens with every launch. It fits a
              narrow column or a thin strip.
    Or once:  File > Scripts > Run Script File...  > pick this file.
    Needs:    Edit > Preferences > Scripting & Expressions >
              "Allow Scripts to Write Files and Access Network" (on).
    Stop:     the Stop / Start button, or close the panel.
*/
(function (thisObj) {
    var SECTION = "ClaudeBridge", KEY = "root";
    function slash(p) { return String(p).replace(/\\/g, "/"); }
    function inScripts(path) { return /\/Scripts(\/(ScriptUI Panels|Startup|Shutdown))?$/i.test(path); }

    var ROOT, INBOX, OUTBOX, DONE;
    function setRoot(path) {
        var r = new Folder(path);
        if (!r.exists && !r.create()) return false;
        var i = new Folder(path + "/inbox"), o = new Folder(path + "/outbox"), d = new Folder(path + "/done");
        if (!i.exists) i.create();
        if (!o.exists) o.create();
        if (!d.exists) d.create();
        if (!i.exists || !o.exists || !d.exists) return false;
        ROOT = path; INBOX = i; OUTBOX = o; DONE = d;
        return true;
    }
    function defaultRoot() {
        var here = "";
        try { here = slash(new File($.fileName).parent.fsName); } catch (e) {}
        if (here && !inScripts(here) && setRoot(here)) return here;
        return slash(Folder.myDocuments.fsName) + "/ClaudeBridge";
    }
    var saved = app.settings.haveSetting(SECTION, KEY) ? app.settings.getSetting(SECTION, KEY) : "";
    if (!(saved && setRoot(saved))) setRoot(defaultRoot());

    function q(s) {
        s = String(s);
        var out = '"';
        for (var i = 0; i < s.length; i++) {
            var c = s.charAt(i), code = s.charCodeAt(i);
            if (c === '"') out += '\\"';
            else if (c === '\\') out += '\\\\';
            else if (c === '\n') out += '\\n';
            else if (c === '\r') out += '\\r';
            else if (c === '\t') out += '\\t';
            else if (code < 32) out += '\\u' + ('0000' + code.toString(16)).slice(-4);
            else out += c;
        }
        return out + '"';
    }
    function stringify(v, depth) {
        depth = depth || 0;
        if (depth > 60) return '"<max depth>"';
        if (v === null || v === undefined) return 'null';
        var t = typeof v;
        if (t === 'number') return isFinite(v) ? String(Math.round(v * 10000) / 10000) : 'null';
        if (t === 'boolean') return v ? 'true' : 'false';
        if (t === 'string') return q(v);
        if (t === 'function') return 'null';
        if (v instanceof Array) {
            var a = [];
            for (var i = 0; i < v.length; i++) a.push(stringify(v[i], depth + 1));
            return '[' + a.join(',') + ']';
        }
        if (t === 'object') {
            var parts = [];
            for (var k in v) {
                if (!v.hasOwnProperty || v.hasOwnProperty(k)) parts.push(q(k) + ':' + stringify(v[k], depth + 1));
            }
            return '{' + parts.join(',') + '}';
        }
        return q(String(v));
    }
    function readText(f) { f.encoding = "UTF-8"; f.open("r"); var s = f.read(); f.close(); return s; }
    function writeText(f, s) { f.encoding = "UTF-8"; f.open("w"); f.write(s); f.close(); }
    function readBinary(f) { f.encoding = "BINARY"; f.open("r"); var s = f.read(); f.close(); return s; }

    // HMAC-SHA256 over byte strings (one char per byte, 0-255): AE has no crypto API
    var SHA_K = [
        0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
        0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
        0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
        0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
        0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
        0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
        0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
        0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2];
    function sha256(bytes) {
        var H = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19];
        var l = bytes.length, n = ((l + 8) >> 6) * 16 + 16, w = [], W = [], i, j;
        for (i = 0; i < n; i++) w[i] = 0;
        for (i = 0; i < l; i++) w[i >> 2] |= (bytes.charCodeAt(i) & 0xff) << (24 - (i % 4) * 8);
        w[l >> 2] |= 0x80 << (24 - (l % 4) * 8);
        w[n - 1] = l * 8;
        for (j = 0; j < n; j += 16) {
            var a = H[0], b = H[1], c = H[2], d = H[3], e = H[4], f = H[5], g = H[6], h = H[7];
            for (i = 0; i < 64; i++) {
                if (i < 16) W[i] = w[j + i];
                else {
                    var x = W[i - 15], y = W[i - 2];
                    W[i] = (W[i - 16] + (((x >>> 7) | (x << 25)) ^ ((x >>> 18) | (x << 14)) ^ (x >>> 3)) +
                        W[i - 7] + (((y >>> 17) | (y << 15)) ^ ((y >>> 19) | (y << 13)) ^ (y >>> 10))) | 0;
                }
                var t1 = (h + (((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7))) +
                    ((e & f) ^ (~e & g)) + SHA_K[i] + W[i]) | 0;
                var t2 = ((((a >>> 2) | (a << 30)) ^ ((a >>> 13) | (a << 19)) ^ ((a >>> 22) | (a << 10))) +
                    ((a & b) ^ (a & c) ^ (b & c))) | 0;
                h = g; g = f; f = e; e = (d + t1) | 0; d = c; c = b; b = a; a = (t1 + t2) | 0;
            }
            H[0] = (H[0] + a) | 0; H[1] = (H[1] + b) | 0; H[2] = (H[2] + c) | 0; H[3] = (H[3] + d) | 0;
            H[4] = (H[4] + e) | 0; H[5] = (H[5] + f) | 0; H[6] = (H[6] + g) | 0; H[7] = (H[7] + h) | 0;
        }
        var out = "";
        for (i = 0; i < 8; i++) for (j = 24; j >= 0; j -= 8) out += String.fromCharCode((H[i] >>> j) & 0xff);
        return out;
    }
    function hmacHex(key, msg) {
        if (key.length > 64) key = sha256(key);
        var ipad = "", opad = "", i;
        for (i = 0; i < 64; i++) {
            var k = i < key.length ? key.charCodeAt(i) : 0;
            ipad += String.fromCharCode(k ^ 0x36); opad += String.fromCharCode(k ^ 0x5c);
        }
        var d = sha256(opad + sha256(ipad + msg)), hex = "";
        for (i = 0; i < d.length; i++) hex += ("0" + d.charCodeAt(i).toString(16)).slice(-2);
        return hex;
    }

    // send.sh puts "// claude-bridge-sig <unix time> <hex>" on the first line, the HMAC of
    // "<time>\n<name>\n<rest of the file bytes>" with the key file's text. Returns {src} or {error}.
    var KEY_FILE = new File(Folder("~").fsName + "/.claude/ae-bridge.key"), MAX_AGE = 3600;
    function verify(name, raw, seen) {
        if (!KEY_FILE.exists) return { error: "no key file " + KEY_FILE.fsName + " (send.sh creates it)" };
        var key = readText(KEY_FILE).replace(/\s+/g, "");
        if (key.length < 32) return { error: "key file is too short" };
        var nl = raw.indexOf("\n");
        var m = nl < 0 ? null : /^\/\/ claude-bridge-sig (\d+) ([0-9a-f]{64})\r?$/.exec(raw.substring(0, nl));
        if (!m) return { error: "not signed (send it with send.sh)" };
        var body = raw.substring(nl + 1);
        if (hmacHex(key, m[1] + "\n" + name + "\n" + body) !== m[2]) return { error: "bad signature (changed after signing, or another key)" };
        var age = new Date().getTime() / 1000 - Number(m[1]);
        if (age > MAX_AGE || age < -300) return { error: "signature expired (" + Math.round(age) + " s old), send it again" };
        if (seen[m[2]]) return { error: "already run once" };
        try { body = decodeURIComponent(escape(body)); } catch (e) { return { error: "not valid UTF-8" }; }
        seen[m[2]] = true;
        return { src: body.replace(/^﻿/, "") };
    }

    var B = $.global.ClaudeBridge;
    if (B && B.taskId) { try { app.cancelTask(B.taskId); } catch (e) {} }
    var seen = (B && B.seen) || {};   // survives reopening the panel, so a run script can't be replayed
    B = $.global.ClaudeBridge = { busy: false, paused: false, taskId: 0, count: 0, stringify: stringify, readText: readText, writeText: writeText, ROOT: ROOT, seen: seen };

    // ---------- UI ----------
    // the button and status share the top row, so the panel still works shrunk to a strip or docked
    // as a tab; the log below takes whatever height is left. Not docked, it is a "window" (not a
    // palette): AE makes palettes tool windows, which Windows gives no minimize button.
    var win = (thisObj instanceof Panel) ? thisObj : new Window("window", "Claude Bridge", undefined, { resizeable: true, minimizeButton: true });
    win.orientation = "column"; win.alignChildren = ["fill", "top"]; win.margins = 6; win.spacing = 4;
    var row = win.add("group"); row.alignment = ["fill", "top"]; row.spacing = 6;
    var runBtn = row.add("button", undefined, "Stop");
    var status = row.add("statictext", undefined, "", { truncate: "end" });
    status.alignment = ["fill", "center"]; status.preferredSize = [220, 18]; status.minimumSize = [40, 18];
    var log = win.add("edittext", undefined, "", { multiline: true, readonly: true, scrolling: true });
    log.alignment = ["fill", "fill"]; log.preferredSize = [480, 120]; log.minimumSize = [40, 0];
    function addLog(s) { var d = new Date(); var ts = ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2) + ':' + ('0' + d.getSeconds()).slice(-2); log.text = ts + "  " + s + "\n" + log.text; }
    function idle() {
        status.text = (B.paused ? "Stopped" : "Listening…") + " (inbox: " + INBOX.fsName + ")" + (B.count ? "  ·  " + B.count + " run" : "");
        status.helpTip = INBOX.fsName;
    }
    // a docked panel that was closed leaves its controls invalid; the task must not keep firing then
    function alive() { try { status.text = status.text; return true; } catch (e) { return false; } }
    B.log = addLog;
    B.win = win;

    // switch to another bridge folder and remember it (the panel has no folder button: Claude does
    // this on request); returns "" or the reason it failed. The calling script's own result still
    // goes to the folder it came from.
    B.useFolder = function (path) {
        path = slash(path);
        if (inScripts(path)) return "pick a folder outside After Effects' Scripts folders";
        if (!setRoot(path)) return "can't write to " + path;
        app.settings.saveSetting(SECTION, KEY, ROOT);
        B.ROOT = ROOT;
        addLog("Folder: " + new Folder(ROOT).fsName);
        idle();
        return "";
    };

    B.tick = function () {
        if (!alive()) { try { app.cancelTask(B.taskId); } catch (e) {} return; }
        if (B.busy || B.paused) return;
        var files = INBOX.getFiles("*.jsx");
        if (!files || !files.length) return;
        files.sort(function (a, b) { return a.name < b.name ? -1 : 1; });
        var outDir = OUTBOX, doneDir = DONE, rejDir = new Folder(OUTBOX.parent.fsName + "/rejected");
        B.busy = true;
        try {
            for (var i = 0; i < files.length; i++) {
                var f = files[i], name = f.name.replace(/\.jsx$/i, "");
                var t0 = new Date().getTime(), out = { file: f.name, ok: true };
                var check = verify(name, readBinary(f), seen);
                if (check.error) {
                    out.ok = false; out.rejected = true; out.error = "Rejected: " + check.error;
                    writeText(new File(outDir.fsName + "/" + name + ".json"), stringify(out));
                    if (!rejDir.exists) rejDir.create();
                    var rej = new File(rejDir.fsName + "/" + f.name);
                    if (rej.exists) rej.remove();
                    f.copy(rej); f.remove();
                    addLog("REJECTED " + f.name + " – " + check.error);
                    continue;
                }
                status.text = "Running " + f.name + "…";
                var src = check.src;
                app.beginUndoGroup("Claude: " + name);
                try {
                    var res = eval("(function(){\n" + src + "\n})();");
                    out.result = res;
                } catch (err) {
                    out.ok = false; out.error = err.toString(); out.line = err.line;
                } finally {
                    app.endUndoGroup();
                }
                out.ms = new Date().getTime() - t0;
                writeText(new File(outDir.fsName + "/" + name + ".json"), stringify(out));
                writeText(new File(doneDir.fsName + "/" + f.name), src);   // kept without the signature line
                f.remove();
                B.count++;
                addLog((out.ok ? "OK   " : "FAIL ") + f.name + " (" + out.ms + " ms)" + (out.ok ? "" : " – " + out.error));
            }
        } catch (e2) {
            addLog("Bridge error: " + e2.toString());
        }
        B.busy = false;
        idle();
    };
    runBtn.onClick = function () {
        B.paused = !B.paused;
        runBtn.text = B.paused ? "Start" : "Stop";
        addLog(B.paused ? "Stopped" : "Started");
        idle();
    };

    B.taskId = app.scheduleTask("if ($.global.ClaudeBridge) $.global.ClaudeBridge.tick();", 1000, true);
    win.onResizing = win.onResize = function () { this.layout.resize(); };
    if (win instanceof Window) {
        win.onClose = function () { try { app.cancelTask(B.taskId); } catch (e) {} B.paused = true; };
        win.center(); win.show();
    } else { win.layout.layout(true); win.layout.resize(); }
    idle();
    addLog("Bridge started in " + new Folder(ROOT).fsName + " – signed scripts only" +
        (KEY_FILE.exists ? "" : " (no key yet: send.sh creates it)"));
})(this);
