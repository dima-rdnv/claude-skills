/*  Claude Bridge for After Effects
    --------------------------------
    Lets Claude (Cowork) drive After Effects without an MCP server.
    While this panel is open it checks  <bridge folder>\inbox  every second,
    runs any .jsx file it finds there (one undo step each, named "Claude: <file>"),
    writes the result to  outbox\<file>.json  and moves the script to  done\.

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

    var B = $.global.ClaudeBridge;
    if (B && B.taskId) { try { app.cancelTask(B.taskId); } catch (e) {} }
    B = $.global.ClaudeBridge = { busy: false, paused: false, taskId: 0, count: 0, stringify: stringify, readText: readText, writeText: writeText, ROOT: ROOT };

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
        var outDir = OUTBOX, doneDir = DONE;
        B.busy = true;
        try {
            for (var i = 0; i < files.length; i++) {
                var f = files[i], name = f.name.replace(/\.jsx$/i, "");
                var t0 = new Date().getTime(), out = { file: f.name, ok: true };
                status.text = "Running " + f.name + "…";
                var src = readText(f);
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
                var dest = new File(doneDir.fsName + "/" + f.name);
                if (dest.exists) dest.remove();
                f.copy(dest); f.remove();
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
    addLog("Bridge started in " + new Folder(ROOT).fsName);
})(this);
