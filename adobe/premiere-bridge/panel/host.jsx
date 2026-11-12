/*  Claude Bridge for Premiere Pro - ExtendScript side
    --------------------------------------------------
    Lets Claude drive Premiere Pro without an MCP server.
    The Claude Bridge panel (Window > Extensions > Claude Bridge) calls ClaudeBridge.tick() about
    once a second. Each tick runs every .jsx file in  D:\WORK\Claude\premiere-bridge\inbox  inside
    (function(){ ... })() so a top-level `return` works, writes the result to
    outbox\<file>.json = {file, ok, result | error+line, ms} and moves the script to done\.
    Every few seconds it also writes status.json; a stale "time" there means the panel is closed.

    Premiere has no scriptable undo groups, so a bridge script is not one undo step.
    Install: scripts/install.ps1, restart Premiere, open the panel.
*/
// No newline after "{": err.line then matches the line in the script file.
function __claudeBridgeRun(__src) {
    return eval("(function(){" + __src + "\n})();");
}

(function () {
    var ROOT = "D:/WORK/Claude/premiere-bridge";
    var VERSION = "1.0.0";
    var INBOX = new Folder(ROOT + "/inbox");
    var OUTBOX = new Folder(ROOT + "/outbox");
    var DONE = new Folder(ROOT + "/done");
    var base = new Folder(ROOT);
    if (!base.exists) base.create();
    if (!INBOX.exists) INBOX.create();
    if (!OUTBOX.exists) OUTBOX.create();
    if (!DONE.exists) DONE.create();

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
    // Plain objects and arrays only. Premiere DOM objects come out as "<ClassName>": copy the
    // fields you need into a plain object instead of returning the DOM object itself.
    function stringify(v, depth) {
        depth = depth || 0;
        if (depth > 40) return '"<max depth>"';
        if (v === null || v === undefined) return 'null';
        var t = typeof v;
        if (t === 'number') return isFinite(v) ? String(Math.round(v * 1000000) / 1000000) : 'null';
        if (t === 'boolean') return v ? 'true' : 'false';
        if (t === 'string') return q(v);
        if (t === 'function') return 'null';
        if (v instanceof Array) {
            var a = [];
            for (var i = 0; i < v.length; i++) a.push(stringify(v[i], depth + 1));
            return '[' + a.join(',') + ']';
        }
        if (v instanceof Date) return q(v.toString());
        if (t === 'object') {
            if (v.constructor !== Object) return q('<' + (v.reflect ? v.reflect.name : String(v)) + '>');
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
    function projectName() { try { return app.project ? app.project.name : null; } catch (e) { return null; } }

    var prev = $.global.ClaudeBridge;
    var B = $.global.ClaudeBridge = {
        ROOT: ROOT, VERSION: VERSION, count: prev ? prev.count : 0, messages: [],
        stringify: stringify, readText: readText, writeText: writeText,
        log: function (s) { B.messages.push(String(s)); }
    };

    function beat(state, file) {
        var s = { state: state, time: new Date().getTime(), bridge: VERSION,
                  premiere: app.version, project: projectName(), runs: B.count };
        if (file) s.file = file;
        writeText(new File(ROOT + "/status.json"), stringify(s));
    }

    function runInbox() {
        var ran = [], files = INBOX.getFiles("*.jsx");
        if (!files || !files.length) return ran;
        files.sort(function (a, b) { return a.name < b.name ? -1 : 1; });
        for (var i = 0; i < files.length; i++) {
            var f = files[i], name = f.name.replace(/\.jsx$/i, "");
            var src = readText(f);
            // A file caught while still being written reads as empty: leave it for a later tick.
            if (!src.length && new Date().getTime() - f.modified.getTime() < 3000) continue;
            // Claim the script before running it: one that hangs Premiere must not run again
            // when the panel next starts.
            var dest = new File(DONE.fsName + "/" + f.name);
            if (dest.exists) dest.remove();
            f.copy(dest); f.remove();
            var t0 = new Date().getTime(), out = { file: f.name, ok: true };
            beat("running", f.name);
            try {
                out.result = __claudeBridgeRun(src);
            } catch (err) {
                out.ok = false; out.error = err.toString(); out.line = err.line;
            }
            out.ms = new Date().getTime() - t0;
            writeText(new File(OUTBOX.fsName + "/" + name + ".json"), stringify(out));
            B.count++;
            ran.push({ file: f.name, ok: out.ok, ms: out.ms, error: out.error });
        }
        return ran;
    }

    // Called by the panel. run: check the inbox; heartbeat: write status.json; paused: state to report.
    B.tick = function (run, heartbeat, paused) {
        var ran = [];
        B.messages = [];
        try {
            if (run) ran = runInbox();
            if (heartbeat || ran.length) beat(paused ? "paused" : "listening");
        } catch (e) {
            return stringify({ error: "Bridge error: " + e.toString() + " (line " + e.line + ")" });
        }
        return stringify({ ran: ran, runs: B.count, messages: B.messages });
    };
    B.info = function () {
        return stringify({ root: ROOT, bridge: VERSION, premiere: app.version, project: projectName() });
    };
    B.openRoot = function () { new Folder(ROOT).execute(); return "ok"; };

    // Exports one frame of the active sequence to ROOT/frames/<name>.png and returns that path.
    // QE exportFramePNG mangles its path: after a backslash, a digit starts an octal escape (\0 cuts
    // the path), lowercase a-e lose the backslash, and "\F" hung Premiere for good. Forward slashes
    // or a ".png" ending throw. Lowercase f-z after a backslash came through intact.
    B.exportFrame = function (timecode, name) {
        if (!new RegExp("^[f-z][a-z0-9_-]*$").test(name)) throw new Error("frame name must match [f-z][a-z0-9_-]*: " + name);
        var dir = new Folder(ROOT + "/frames");
        if (!dir.exists) dir.create();
        var path = dir.fsName + "\\" + name;
        if (new RegExp("\\\\[0-9a-eF]").test(path)) throw new Error("unsafe for exportFramePNG: " + path);
        app.enableQE();
        var qs = qe.project.getActiveSequence();
        if (!qs) throw new Error("no active sequence");
        if (!qs.exportFramePNG(timecode, path)) throw new Error("exportFramePNG returned false for " + path);
        return path + ".png";
    };
})();
