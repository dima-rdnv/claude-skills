/*  Claude Bridge for After Effects - ExtendScript side of the CEP panel
    -------------------------------------------------------------------
    Lets Claude drive After Effects without an MCP server. The Claude Bridge panel
    (Window > Extensions > Claude Bridge) calls ClaudeBridge.tick() when it sees a script in the
    inbox (it checks the folder itself once a second). Each tick takes every .jsx in <bridge folder>/inbox, checks its signature, moves it to done/ (without the
    signature line) and runs it inside (function(){ ... })() as one undo step named
    "Claude: <file>", then writes outbox/<file>.json = {file, ok, result | error+line, ms}.

    Signed scripts only: send.sh signs each script with ~/.claude/ae-bridge.key (it creates the key
    on first use). Unsigned, changed, over-an-hour-old or already-run scripts are refused and moved
    to rejected/, so nothing else that can write into inbox (another program, a synced folder) can
    run code here.

    Bridge folder: the one set with ClaudeBridge.useFolder(path) (remembered in AE's settings), else
    Documents/ClaudeBridge. bridge.log there records loads, scripts, rejections, Stop/Start and
    errors (last 7 days). The panel writes heartbeat.json every 5 s.

    The timer lives in the panel (Node), not in AE: it watches inbox itself and calls tick() only
    when a script is waiting. A ScriptUI panel's app.scheduleTask timer is dropped for good by the
    first AE dialog; and polling AE every second left a call pending while AE quit, which hung
    AE's shutdown at 0% CPU.
*/
// No newline after "{": err.line then matches the line in the script file.
function __claudeBridgeRun(__src) {
    return eval("(function(){" + __src + "\n})();");
}

(function () {
    var VERSION = "2.1.0", SECTION = "ClaudeBridge", KEY = "root";
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
    var saved = app.settings.haveSetting(SECTION, KEY) ? app.settings.getSetting(SECTION, KEY) : "";
    if (!(saved && setRoot(saved))) setRoot(slash(Folder.myDocuments.fsName) + "/ClaudeBridge");

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

    // ---------- log file + heartbeat ----------
    // bridge.log keeps its last LOG_DAYS days (at most LOG_LINES lines): trimmed at load and every 6 h.
    var INSTANCE = String(new Date().getTime()).slice(-6), lastTrim = 0, LOG_DAYS = 7, LOG_LINES = 5000;
    var messages = [];   // lines for the panel's log, handed over by the next tick
    function pad(n) { return ("0" + n).slice(-2); }
    function stamp(d) { d = d || new Date(); return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) + " " + pad(d.getHours()) + ":" + pad(d.getMinutes()) + ":" + pad(d.getSeconds()); }
    function logLine(s) {
        try {
            var f = new File(ROOT + "/bridge.log");
            f.encoding = "UTF-8"; f.lineFeed = "Unix"; f.open("a"); f.writeln(stamp() + "  [" + INSTANCE + "]  " + s); f.close();
        } catch (e) {}
    }
    function say(s) { logLine(s); messages.push(String(s)); }
    function trimLog() {
        lastTrim = new Date().getTime();
        try {
            var older = new File(ROOT + "/bridge.log.1");   // left by the first logging version
            if (older.exists) older.remove();
            var f = new File(ROOT + "/bridge.log");
            if (!f.exists) return;
            var cutoff = stamp(new Date(lastTrim - LOG_DAYS * 86400000)), lines = readText(f).split("\n"), keep = [];
            for (var i = 0; i < lines.length; i++) {
                var l = lines[i].replace(/\r$/, "");
                if (l && l.substring(0, 19) >= cutoff) keep.push(l);   // lines start "YYYY-MM-DD HH:MM:SS"
            }
            if (keep.length > LOG_LINES) keep = keep.slice(keep.length - LOG_LINES);
            if (keep.length !== lines.length - 1) writeText(f, keep.length ? keep.join("\n") + "\n" : "");
        } catch (e) {}
    }
    var B = $.global.ClaudeBridge;
    if (B && B.taskId) { try { app.cancelTask(B.taskId); } catch (e) {} }   // the old ScriptUI panel's timer, if still alive
    var seen = (B && B.seen) || {};   // survives reloading this file, so a run script can't be replayed
    var runs = (B && B.runs) || 0;
    B = $.global.ClaudeBridge = { VERSION: VERSION, ROOT: ROOT, instance: INSTANCE, seen: seen, runs: runs,
        stringify: stringify, readText: readText, writeText: writeText, logLine: logLine, log: say };
    trimLog();
    var orphan = new File(ROOT + "/orphan.txt");   // left by the ScriptUI version; no timer here to leave one
    if (orphan.exists) orphan.remove();

    // switch to another bridge folder and remember it (Claude does this on request); returns "" or
    // the reason it failed. The calling script's own result still goes to the folder it came from.
    B.useFolder = function (path) {
        path = slash(path);
        if (inScripts(path)) return "pick a folder outside After Effects' Scripts folders";
        var from = ROOT;
        if (!setRoot(path)) return "can't write to " + path;
        app.settings.saveSetting(SECTION, KEY, ROOT);
        B.ROOT = ROOT;
        trimLog();
        logLine("switched here from " + from);
        say("Folder: " + new Folder(ROOT).fsName);
        return "";
    };

    B.info = function () {
        return stringify({ version: VERSION, root: new Folder(ROOT).fsName, instance: INSTANCE, ae: app.version, keyExists: KEY_FILE.exists });
    };

    function runOne(f) {
        var name = f.name.replace(/\.jsx$/i, ""), outDir = OUTBOX, doneDir = DONE;
        var t0 = new Date().getTime(), out = { file: f.name, ok: true };
        var check = verify(name, readBinary(f), seen);
        if (check.error) {
            out.ok = false; out.rejected = true; out.error = "Rejected: " + check.error;
            writeText(new File(outDir.fsName + "/" + name + ".json"), stringify(out));
            var rejDir = new Folder(outDir.parent.fsName + "/rejected");
            if (!rejDir.exists) rejDir.create();
            var rej = new File(rejDir.fsName + "/" + f.name);
            if (rej.exists) rej.remove();
            f.copy(rej); f.remove();
            say("REJECTED " + f.name + " – " + check.error);
            return;
        }
        // claim it before running: a script that takes AE down must not run again after the restart
        writeText(new File(doneDir.fsName + "/" + f.name), check.src);   // kept without the signature line
        f.remove();
        logLine("run " + f.name);
        app.beginUndoGroup("Claude: " + name);
        try {
            out.result = __claudeBridgeRun(check.src);
        } catch (err) {
            out.ok = false; out.error = err.toString(); out.line = err.line;
        } finally {
            app.endUndoGroup();
        }
        out.ms = new Date().getTime() - t0;
        writeText(new File(outDir.fsName + "/" + name + ".json"), stringify(out));
        B.runs++;
        say((out.ok ? "OK   " : "FAIL ") + f.name + " (" + out.ms + " ms)" + (out.ok ? "" : " – " + out.error));
    }

    // The panel calls this when it sees a script in inbox (it watches the folder and writes the
    // heartbeat itself, so AE is left alone while idle) and shows what it returns.
    B.tick = function () {
        try {
            if (new Date().getTime() - lastTrim > 6 * 3600000) trimLog();
            var files = INBOX.getFiles("*.jsx");
            if (files && files.length) {
                files.sort(function (a, b) { return a.name < b.name ? -1 : 1; });
                for (var i = 0; i < files.length; i++) runOne(files[i]);
            }
        } catch (e) {
            say("Bridge error: " + e.toString() + " (line " + e.line + ")");
        }
        var r = stringify({ root: new Folder(ROOT).fsName, runs: B.runs, messages: messages });
        messages = [];
        return r;
    };

    logLine("bridge code loaded (CEP panel, version " + VERSION + ") in " + ROOT + ", AE " + app.version);
})();
