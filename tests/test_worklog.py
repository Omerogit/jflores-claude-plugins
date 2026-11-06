"""The refocus plugin's work log (worklog.py): every reply's work reaches the server, nothing is lost offline, nothing
is sent twice, and a steward's person side never leaves (Omero, 2026-11-06).    python tests/test_worklog.py"""
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WL = os.path.join(ROOT, "plugins", "refocus", "scripts", "worklog.py")
HELLO = os.path.join(ROOT, "plugins", "refocus", "scripts", "hello.py")
HOOKS = os.path.join(ROOT, "plugins", "refocus", "hooks", "hooks.json")
fails = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  -- " + str(detail)[:400]), flush=True)
    if not cond:
        fails.append(name)


tmp = tempfile.mkdtemp(prefix="worklog-")
RH = os.path.join(tmp, "refocus")
os.environ.update(REFOCUS_HOME=RH, REFOCUS_IGNORE_HOUSE_WATCH="1")
os.environ.pop("OFFICE_SEAT", None)
os.environ.pop("REFOCUS_WORKLOG", None)
spec = importlib.util.spec_from_file_location("worklog_under_test", os.environ.get("WORKLOG_UNDER_TEST") or WL)
W = importlib.util.module_from_spec(spec)
spec.loader.exec_module(W)


class Server:
    """The door, as the laptop sees it: stores by line number and drops what it already holds."""
    def __init__(self):
        self.got, self.down, self.calls = {}, False, 0

    def __call__(self, url, key, body):
        self.calls += 1
        if self.down:
            raise OSError("offline")
        assert url.endswith("/v1/worklog") and key == "bd_k"
        size = len(json.dumps(body, ensure_ascii=False).encode("utf-8"))
        self.posts = getattr(self, "posts", []) + [(len(body["entries"]), size)]
        if len(body["entries"]) > 400 or size > 512 * 1024:      # the door's own limits: it refuses, 400
            return 400, {"error": "too big"}
        n = 0
        for e in body["entries"]:
            if (body["session"], e["i"], e["kind"], e["text"]) not in self.got:
                self.got[(body["session"], e["i"], e["kind"], e["text"])] = e
                n += 1
        return 200, {"stored": n, "verify": "PASS"}

    def texts(self, kind=None):
        return [e["text"] for k, e in sorted(self.got.items(), key=lambda kv: kv[0][1]) if kind in (None, e["kind"])]


def rec(kind, content, ts="2026-11-06T15:04:05.000Z"):
    return {"type": kind, "timestamp": ts, "message": {"role": kind, "content": content}}


def write(tp, recs, partial=""):
    with io.open(tp, "a", encoding="utf-8", newline="") as f:
        for r in recs:
            f.write(json.dumps(r) + "\n")
        f.write(partial)


def connect():
    os.makedirs(RH, exist_ok=True)
    with open(os.path.join(RH, "door.json"), "w", encoding="utf-8") as f:
        json.dump({"door": "https://example.test/brain", "key": "bd_k", "partner": "marc-desk"}, f)


try:
    S = Server()
    W.HTTP = S
    tp = os.path.join(tmp, "s1.jsonl")
    write(tp, [{"type": "summary", "summary": "x"},
               rec("user", "Fix Crystal's double booking"),
               rec("assistant", [{"type": "thinking", "thinking": "secret thoughts"},
                                 {"type": "text", "text": "Reading campaign_line.py first."},
                                 {"type": "tool_use", "name": "Edit", "input": {"file_path": "/x/campaign_line.py",
                                                                                "old_string": "a", "new_string": "b"}}]),
               rec("user", [{"type": "tool_result", "content": [{"type": "text", "text": "edited"}]}]),
               rec("assistant", [{"type": "tool_use", "name": "Bash", "input": {"command": "pytest -q"}}])])

    check("not connected: nothing is sent", W.flush("sess-0001", tp) == 0 and S.calls == 0)
    connect()
    n = W.flush("sess-0001", tp, "/Users/marc/crystal")
    check("connected: the ask, the answer, both tool calls and the result are sent",
          n == 5 and S.texts("ask") == ["Fix Crystal's double booking"] and
          S.texts("answer") == ["Reading campaign_line.py first."] and len(S.texts("tool")) == 2 and
          S.texts("result") == ["edited"], S.got)
    check("thinking never leaves the computer", not any("secret thoughts" in t for t in S.texts()), S.texts())
    check("the edited file's path is in the tool call", any("/x/campaign_line.py" in t for t in S.texts("tool")))
    check("the transcript's UTC time is kept", all(abs(e["ts"] - 1793977445.0) < 1 for e in S.got.values()),
          [e["ts"] for e in S.got.values()])
    calls = S.calls
    check("a second flush with nothing new sends nothing", W.flush("sess-0001", tp) == 0 and S.calls == calls)

    write(tp, [rec("user", "now ship it")], partial='{"type": "assistant", "message": {"content": [{"type": "te')
    W.flush("sess-0001", tp)
    check("a half-written last line waits; the complete one goes", S.texts("ask")[-1] == "now ship it" and
          len(S.got) == 6, S.texts())
    with io.open(tp, "a", encoding="utf-8", newline="") as f:
        f.write('xt", "text": "Shipped."}]}}\n')
    W.flush("sess-0001", tp)
    check("once the line is complete it goes, once", S.texts("answer")[-1] == "Shipped." and len(S.got) == 7,
          S.texts())

    S.down = True
    write(tp, [rec("user", "offline ask")])
    W.flush("sess-0001", tp)
    st = W.load("sess-0001")
    check("offline: the offset does not move", "offline ask" not in S.texts() and st["line"] == 7, st)
    S.down = False
    W.sweep()
    check("back online, the sweep sends what waited", S.texts("ask")[-1] == "offline ask" and len(S.got) == 8,
          S.texts())

    refused = Server()
    W.HTTP = lambda u, k, b: (429, {"error": "too many requests"})
    write(tp, [rec("user", "after a refusal")])
    W.flush("sess-0001", tp)
    W.HTTP = S
    W.flush("sess-0001", tp)
    check("a refusal (429) keeps the line for the next send", S.texts("ask")[-1] == "after a refusal")

    # batching: many big entries split into batches, all arrive once, in order
    tp2 = os.path.join(tmp, "s2.jsonl")
    write(tp2, [rec("assistant", [{"type": "text", "text": ("%04d " % k) + "y" * 9000}]) for k in range(120)])
    S2 = Server()
    W.HTTP = S2
    W.flush("sess-0002", tp2)
    got = sorted(e["i"] for e in S2.got.values())
    check("a long session goes in several batches, every line once", got == list(range(1, 121)) and S2.calls > 1,
          (len(got), S2.calls))
    calls = S2.calls
    W.flush("sess-0002", tp2)
    check("and is never sent twice", S2.calls == calls)

    # the steward's person side never leaves
    tp3 = os.path.join(tmp, "s3.jsonl")
    write(tp3, [rec("user", "/steward:start"),
                rec("assistant", [{"type": "tool_use", "name": "Bash",
                                   "input": {"command": "python steward.py brief --slot faith"}}])])
    S3 = Server()
    W.HTTP = S3
    W.flush("sess-0003", tp3)
    check("a steward interview session sends nothing at all", S3.calls == 0 and W.load("sess-0003")["private"])
    write(tp3, [rec("user", "unrelated work later")])
    W.flush("sess-0003", tp3)
    check("and stays private for the rest of the session", S3.calls == 0)
    tp4 = os.path.join(tmp, "s4.jsonl")
    write(tp4, [rec("user", "a work question"),
                rec("assistant", [{"type": "tool_use", "name": "Bash",
                                   "input": {"command": "python steward.py note --side person --title x"}}])])
    W.flush("sess-0004", tp4)
    check("a person-side note anywhere in the unsent lines stops the whole send", S3.calls == 0)

    # r2 (Nathan and Shallum's hold, 11-06): a record bigger than a batch is sent whole, in pieces, never cut short
    tp6 = os.path.join(tmp, "s6.jsonl")
    write(tp6, [rec("user", "run them all"),
                rec("assistant", [{"type": "tool_use", "name": "Bash", "input": {"command": "echo %d" % k}}
                                  for k in range(305)]),
                rec("user", "after the big one")])
    S6 = Server()
    W.HTTP = S6
    W.flush("sess-0006", tp6)
    cmds = [e for e in S6.got.values() if e["kind"] == "tool"]
    check("one record of 305 tool calls (batch limit 300) arrives whole: 305 calls, then the next line",
          len(cmds) == 305 and len({(e["i"], e["j"]) for e in cmds}) == 305 and
          S6.texts("ask")[-1] == "after the big one", (len(cmds), S6.calls))
    calls = S6.calls
    W.flush("sess-0006", tp6)
    check("and nothing of it is sent twice", S6.calls == calls)
    tp7 = os.path.join(tmp, "s7.jsonl")
    write(tp7, [rec("assistant", [{"type": "text", "text": ("%02d" % k) + "x" * 19000} for k in range(25)]),
                rec("user", "next")])
    S7 = Server()
    W.HTTP = S7
    W.flush("sess-0007", tp7)
    check("one record over 350 KB goes in pieces, every piece once", len([e for e in S7.got.values()
          if e["kind"] == "answer"]) == 25 and S7.texts("ask") == ["next"] and S7.calls >= 2, S7.calls)
    tp8 = os.path.join(tmp, "s8.jsonl")
    write(tp8, [rec("user", "a"), rec("assistant", [{"type": "text", "text": "b%d" % k} for k in range(4)] +
                                     [{"type": "tool_use", "name": "Bash", "input": {"command": "c%d" % k}}
                                      for k in range(3)]), rec("user", "d")])
    saved = W.BATCH_ENTRIES
    W.BATCH_ENTRIES = 3
    S8 = Server()
    W.HTTP = S8
    W.flush("sess-0008", tp8)
    W.BATCH_ENTRIES = saved
    check("Shallum's case: seven entries on one line, batch size 3, all nine arrive",
          len(S8.got) == 9 and sorted(S8.texts("tool")) == ['{"command": "c0"}', '{"command": "c1"}',
                                                             '{"command": "c2"}'], S8.texts())

    # masking on this computer, before the cut
    M = W.mask
    cases = {
        "an Anthropic key": ("export ANTHROPIC_API_KEY=sk-ant-api03-abcdefghijklmnopqrstuvwxyz0123", "sk-ant-api03"),
        "a short labelled password": ("password=hunter2", "hunter2"),
        "a JSON password": ('{"password": "Tr0ub4dor"}', "Tr0ub4dor"),
        "curl -u": ("curl -u admin:s3cretpass https://x", "s3cretpass"),
        "sshpass -p": ("sshpass -p 'Pa55word!' ssh me@host", "Pa55word"),
        "mysql -p": ("mysql -uroot -pS3cretPass db", "S3cretPass"),
        "a cookie header": ("Cookie: session=abc123def456; hcp=zz99", "abc123def456"),
        "a set-cookie": ("set-cookie: hcp_session=Q1w2E3r4; Path=/", "Q1w2E3r4"),
        "a session id": ("session_id=9f8e7d6c5b", "9f8e7d6c5b"),
        "a bearer token": ("Authorization: Bearer abcdefghijklmnopqrstuvwxyz123456", "abcdefghijklmnop"),
        "a card number": ("card 4111 1111 1111 1111 exp", "4111 1111 1111 1111"),
        "a door key": ("key bd_" + "Q" * 30, "bd_QQQQ"),
        "a URL with a password": ("postgres://app:hunter22@db/x", "hunter22"),
        "an Authorization: Token header (HCP's API form)": (
            "curl -H 'Authorization: Token abcdef0123456789abcdef' https://api.housecallpro.com/jobs",
            "abcdef0123456789abcdef"),
        "an Authorization: Basic header": ("Authorization: Basic dXNlcjpwYXNzd29yZDEyMw==", "dXNlcjpwYXNz"),
        "a cookie header with unlabelled values": ("Cookie: _ga=GA1.2.33; hcpweb=Zq9Xw8kL", "Zq9Xw8kL"),
    }
    for name, (text, secret) in cases.items():
        check("masked on this computer: " + name, secret not in M(text) and "[masked]" in M(text), M(text))
    kept = ["Job 14215 is on the board", "2032 passed, 26/26 mutants", "call (956) 392-3423",
            "session = requests.Session()", "token = os.environ['HCP_TOKEN']", "password: None",
            "commit 1d28c7454ea8 over b0cbcd6955d5", "epoch 1793977445123"]
    for t in kept:
        check("kept whole: " + t, M(t) == t, M(t))
    tp9 = os.path.join(tmp, "s9.jsonl")
    key = "ghp_" + "A1b2C3d4E5" * 4
    write(tp9, [rec("user", [{"type": "tool_result", "content": "x" * (2000 - 11) + " " + key}])])
    S9 = Server()
    W.HTTP = S9
    W.flush("sess-0009", tp9)
    res = S9.texts("result")[0]
    check("a key that straddles the 2,000-character cut leaves no prefix behind (masked, then cut)",
          "ghp_" not in res and "A1b2C3" not in res and len(res) <= 2000, res[-40:])

    pem = ("-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAAB\n"
           "QyNTUxOQAAACDx1y2z3W4v5U6t7S8r9Q0p1O2n3M4l5K6j7I8h9G0f1E\n-----END OPENSSH PRIVATE KEY-----\nafter")
    check("a private key's whole block is masked, not just its BEGIN line",
          "b3BlbnNzaC1rZXkt" not in M(pem) and "QyNTUxOQ" not in M(pem) and "END OPENSSH" not in M(pem) and
          M(pem).endswith("after"), M(pem))
    check("a cut-off private key block (no END line) is masked to the end",
          "b3BlbnNzaC1rZXkt" not in M(pem.split("-----END")[0]), M(pem.split("-----END")[0]))

    # r3: every post fits the door's limits, and a batch never takes a record that won't fit
    tp11 = os.path.join(tmp, "s11.jsonl")
    write(tp11, [rec("assistant", [{"type": "tool_use", "name": "Bash", "input": {"command": "a%d" % k}}
                                   for k in range(200)]),
                 rec("assistant", [{"type": "tool_use", "name": "Bash", "input": {"command": "b%d" % k}}
                                   for k in range(200)])])
    S11 = Server()
    W.HTTP = S11
    W.flush("sess-0011", tp11)
    check("two records of 200 at a batch limit of 300 go as 200 and 200, never 400 in one post",
          [n for n, _ in S11.posts] == [200, 200] and len(S11.got) == 400, S11.posts)
    check("no post in any of these runs broke the door's limits (400 entries, 512 KB)",
          all(n <= 400 and b <= 512 * 1024 for s_ in (S6, S7, S11) for n, b in s_.posts), [s_.posts for s_ in (S6, S7)])
    check("the record over 350 KB went in pieces that each fit 350 KB",
          all(b <= W.BATCH_BYTES + 4096 for _, b in S7.posts), S7.posts)

    # off the record
    tp10 = os.path.join(tmp, "s10.jsonl")
    write(tp10, [rec("user", "fix the build"), rec("assistant", [{"type": "text", "text": "done"}])])
    S10 = Server()
    W.HTTP = S10
    W.flush("sess-0010", tp10)
    write(tp10, [rec("user", "Off the record, can I talk about my dad for a minute?"),
                 rec("assistant", [{"type": "text", "text": "Of course."}])])
    W.flush("sess-0010", tp10)
    write(tp10, [rec("user", "back to the build")])
    W.flush("sess-0010", tp10)
    check("'off the record' stops the session: the work before it went, nothing after it does",
          S10.texts("ask") == ["fix the build"] and "Of course." not in S10.texts() and W.load("sess-0010")["private"],
          S10.texts())
    for k, words in enumerate(["this is off-the-record", "OFF  THE  RECORD please", "off_the_record: my health",
                               "can we talk off the record?"]):
        tpk = os.path.join(tmp, "s12-%d.jsonl" % k)
        write(tpk, [rec("user", words), rec("assistant", [{"type": "text", "text": "ok"}])])
        Sk = Server()
        W.HTTP = Sk
        W.flush("sess-0012-%d" % k, tpk)
        check("'off the record' in another spelling still stops it: %r" % words, Sk.calls == 0, Sk.texts())
    check("'record' alone, or 'on the record', does not stop a session",
          not W.OFF_RECORD_RX.search("log the record count") and not W.OFF_RECORD_RX.search("on the record"))

    # kill switch and house machines
    tp5 = os.path.join(tmp, "s5.jsonl")
    write(tp5, [rec("user", "hello")])
    os.environ["REFOCUS_WORKLOG"] = "off"
    W.flush("sess-0005", tp5)
    check("REFOCUS_WORKLOG=off sends nothing", S3.calls == 0)
    os.environ.pop("REFOCUS_WORKLOG")
    os.environ["OFFICE_SEAT"] = "zen"
    os.environ.pop("REFOCUS_IGNORE_HOUSE_WATCH")
    W.flush("sess-0005", tp5)
    check("a house seat never sends (its work is already on the server)", S3.calls == 0)
    os.environ.pop("OFFICE_SEAT")
    os.environ["REFOCUS_IGNORE_HOUSE_WATCH"] = "1"

    # the hook: returns at once, never blocks the turn, never prints
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, WL], input=json.dumps({"session_id": "sess-0006", "transcript_path":
                       os.path.join(tmp, "missing.jsonl")}), env=env, capture_output=True, text=True, timeout=20)
    check("the Stop hook exits 0 and prints nothing", r.returncode == 0 and r.stdout == "", (r.returncode, r.stdout))
    r = subprocess.run([sys.executable, WL], input="not json", env=env, capture_output=True, text=True, timeout=20)
    check("a bad event still exits 0", r.returncode == 0)

    hooks = json.load(open(HOOKS, encoding="utf-8"))["hooks"]
    check("hooks.json runs worklog.cmd on Stop", any("worklog.cmd" in h["command"] for g in hooks.get("Stop", [])
                                                     for h in g["hooks"]), hooks.get("Stop"))
    stub = open(os.path.join(os.path.dirname(WL), "worklog.cmd"), encoding="utf-8").read()
    check("worklog.cmd is the two-line polyglot every hook uses", stub.splitlines() == [
        ':; hook_target=worklog.py; . "$CLAUDE_PLUGIN_ROOT/scripts/hook_launch.cmd"',
        '@"%~dp0hook_launch.cmd" worklog.py'], stub)

    # told once
    r1 = subprocess.run([sys.executable, HELLO], input="{}", env=env, capture_output=True, text=True, timeout=30)
    r2 = subprocess.run([sys.executable, HELLO], input="{}", env=env, capture_output=True, text=True, timeout=30)
    check("the person is told once, the first session", "J FLORES WORK LOG" in r1.stdout and
          "J FLORES WORK LOG" not in r2.stdout, (r1.stdout[-300:], r2.stdout[-300:]))
    check("the telling names what goes, the masking and the steward's private side",
          all(w in r1.stdout for w in ("files changed", "blanked out", "Faithful Steward", "ONCE", "off the record",
                                       "Only Omero and Monday")), r1.stdout[-900:])
    shutil.rmtree(os.path.join(RH, "worklog"), ignore_errors=True)
    r3 = subprocess.run([sys.executable, HELLO], input="{}", env=dict(env, REFOCUS_WORKLOG="off"),
                        capture_output=True, text=True, timeout=30)
    check("with the kill switch on, nobody is told", "J FLORES WORK LOG" not in r3.stdout)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\n%s: %d failed" % ("ALL PASS" if not fails else "FAILURES", len(fails)))
sys.exit(1 if fails else 0)
