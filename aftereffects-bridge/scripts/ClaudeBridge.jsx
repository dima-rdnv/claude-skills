/*  Claude Bridge for After Effects
    --------------------------------
    Lets Claude (Cowork) drive After Effects without an MCP server.
    While this panel is open it checks  inbox\  next to this file every second,
    runs any .jsx file it finds there (one undo step each, named "Claude: <file>"),
    writes the result to  outbox\<file>.json  and moves the script to  done\.
    If this file's folder is read-only, it uses  Documents\ClaudeBridge  instead.

    Start:  File > Scripts > Run Script File...  > pick this file.
    Needs:  Edit > Preferences > Scripting & Expressions >
            "Allow Scripts to Write Files and Access Network" (on).
    Stop:   close the panel (or press Pause).
*/
(function (thisObj) {
    function slash(p) { return String(p).replace(/\\/g, "/"); }
    var ROOT = "";
    try { ROOT = slash(new File($.fileName).parent.fsName); } catch (e) {}
    if (!ROOT || !(new Folder(ROOT + "/inbox").exists || new Folder(ROOT + "/inbox").create())) {
        ROOT = slash(Folder.myDocuments.fsName) + "/ClaudeBridge";
        new Folder(ROOT).create();
    }
    var INBOX = new Folder(ROOT + "/inbox");
    var OUTBOX = new Folder(ROOT + "/outbox");
    var DONE = new Folder(ROOT + "/done");
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
    var win = (thisObj instanceof Panel) ? thisObj : new Window("palette", "Claude Bridge", undefined, { resizeable: true });
    win.orientation = "column"; win.alignChildren = ["fill", "top"]; win.margins = 10; win.spacing = 6;
    var status = win.add("statictext", undefined, "Listening… (inbox: " + INBOX.fsName + ")", { truncate: "end" });
    status.preferredSize = [360, 18];
    var log = win.add("edittext", undefined, "", { multiline: true, readonly: true, scrolling: true });
    log.preferredSize = [360, 140];
    var row = win.add("group"); row.alignment = ["fill", "top"];
    var pauseBtn = row.add("button", undefined, "Pause");
    var runBtn = row.add("button", undefined, "Check now");
    function addLog(s) { var d = new Date(); var ts = ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2) + ':' + ('0' + d.getSeconds()).slice(-2); log.text = ts + "  " + s + "\n" + log.text; }
    B.log = addLog;

    B.tick = function () {
        if (B.busy || B.paused) return;
        var files = INBOX.getFiles("*.jsx");
        if (!files || !files.length) return;
        files.sort(function (a, b) { return a.name < b.name ? -1 : 1; });
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
                writeText(new File(OUTBOX.fsName + "/" + name + ".json"), stringify(out));
                var dest = new File(DONE.fsName + "/" + f.name);
                if (dest.exists) dest.remove();
                f.copy(dest); f.remove();
                B.count++;
                addLog((out.ok ? "OK   " : "FAIL ") + f.name + " (" + out.ms + " ms)" + (out.ok ? "" : " – " + out.error));
            }
        } catch (e2) {
            addLog("Bridge error: " + e2.toString());
        }
        B.busy = false;
        status.text = (B.paused ? "Paused" : "Listening…") + "  ·  " + B.count + " run";
    };
    pauseBtn.onClick = function () { B.paused = !B.paused; pauseBtn.text = B.paused ? "Resume" : "Pause"; status.text = B.paused ? "Paused" : "Listening…"; };
    runBtn.onClick = function () { B.tick(); };

    B.taskId = app.scheduleTask("if ($.global.ClaudeBridge) $.global.ClaudeBridge.tick();", 1000, true);
    if (win instanceof Window) {
        win.onClose = function () { try { app.cancelTask(B.taskId); } catch (e) {} B.paused = true; };
        win.center(); win.show();
    } else { win.layout.layout(true); }
    addLog("Bridge started.");
})(this);
