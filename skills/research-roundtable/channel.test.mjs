import { afterEach, beforeEach, expect, test } from "bun:test"
import { mkdtempSync, readFileSync, rmSync, appendFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { spawn, spawnSync } from "node:child_process"

const helper = join(import.meta.dir, "scripts", "channel.py")
let temporary
let env

beforeEach(() => {
  temporary = mkdtempSync(join(tmpdir(), "research-roundtable-test-"))
  env = { ...process.env, RESEARCH_ROUNDTABLE_DIR: temporary, PYTHONDONTWRITEBYTECODE: "1" }
})

afterEach(() => rmSync(temporary, { recursive: true, force: true }))

function run(args, input) {
  const result = spawnSync("python3", [helper, ...args], {
    env, input, encoding: "utf8", timeout: 5000,
  })
  if (result.error) throw result.error
  if (result.status !== 0) throw new Error(result.stderr || `channel exited ${result.status}`)
  return result.stdout
}

function start(args, input) {
  const child = spawn("python3", [helper, ...args], { env, stdio: ["pipe", "pipe", "pipe"] })
  const done = new Promise((resolve, reject) => {
    let stdout = ""
    let stderr = ""
    child.stdout.on("data", chunk => { stdout += chunk })
    child.stderr.on("data", chunk => { stderr += chunk })
    child.on("error", reject)
    child.on("close", code => code === 0 ? resolve(stdout) : reject(new Error(stderr)))
  })
  child.stdin.end(input)
  return { child, done }
}

test("two identities exchange multiline Unicode messages through stdin", () => {
  run(["setup", "idea-v1", "proposer"])
  run(["setup", "idea-v1", "reviewer"])
  const question = "[HANDSHAKE] 机制是什么？\nReply CHANNEL_OK RRT-01 — 🧪"
  run(["send", "idea-v1", "proposer", "--stdin"], question)
  expect(run(["listen", "idea-v1", "reviewer", "--timeout", "0.2"]).trim())
    .toBe(`[proposer] ${question}`)
  run(["send", "idea-v1", "reviewer", "--stdin"], "CHANNEL_OK RRT-01")
  expect(run(["poll", "idea-v1", "proposer"]).trim()).toBe("[reviewer] CHANNEL_OK RRT-01")
  expect(run(["poll", "idea-v1", "reviewer"])).toBe("")
  expect(JSON.parse(run(["status", "idea-v1", "reviewer"])).pending_lines).toBe(0)
})

test("each reader has an independent cursor and history does not consume messages", () => {
  for (const identity of ["writer", "first", "second"]) run(["setup", "cursors", identity])
  run(["send", "cursors", "writer", "hello"])
  expect(run(["history", "cursors", "first"]).trim()).toBe("[writer] hello")
  expect(run(["poll", "cursors", "first"]).trim()).toBe("[writer] hello")
  expect(run(["poll", "cursors", "second"]).trim()).toBe("[writer] hello")
  expect(run(["poll", "cursors", "first"])).toBe("")
  expect(run(["poll", "cursors", "writer"])).toBe("")
})

test("channels isolate transcripts and a timed receive returns when no peer answers", () => {
  run(["setup", "one", "reviewer"])
  run(["setup", "two", "reviewer"])
  run(["send", "one", "proposer", "one-only"])
  expect(run(["listen", "two", "reviewer", "--timeout", "0.1", "--interval", "0.05"])).toBe("")
  expect(run(["poll", "one", "reviewer"]).trim()).toBe("[proposer] one-only")
})

test("a waiting receiver returns a message sent by another process", async () => {
  run(["setup", "waiting", "reviewer"])
  const receiver = start(["wait", "waiting", "reviewer", "--interval", "0.05"])
  const deadline = setTimeout(() => receiver.child.kill(), 4000)
  try {
    run(["send", "waiting", "proposer", "arrived"])
    expect((await receiver.done).trim()).toBe("[proposer] arrived")
  } finally {
    clearTimeout(deadline)
    if (receiver.child.exitCode === null) receiver.child.kill()
  }
}, 6000)

test("concurrent senders produce complete JSON records without losing messages", async () => {
  run(["setup", "concurrent", "reviewer"])
  const messages = Array.from({ length: 12 }, (_, i) => `message ${i}: ${"讨论🧪".repeat(400)}`)
  await Promise.all(messages.map((message, i) =>
    start(["send", "concurrent", `writer-${i}`, "--stdin"], message).done))
  const records = readFileSync(join(temporary, "concurrent.ndjson"), "utf8").trim().split("\n").map(JSON.parse)
  expect(records).toHaveLength(messages.length)
  expect(new Set(records.map(record => record.text))).toEqual(new Set(messages))
  expect(new Set(records.map(record => record.from)).size).toBe(messages.length)
})

test("unsafe names and empty messages are rejected without appending records", () => {
  for (const name of ["../escape", "bad/name", "bad\\name", "a b", "a".repeat(81)]) {
    const result = spawnSync("python3", [helper, "setup", name, "reader"], { env, encoding: "utf8" })
    expect(result.status).not.toBe(0)
    expect(result.stderr).toContain("invalid channel")
  }
  const identity = spawnSync("python3", [helper, "setup", "valid", "../escape"], { env, encoding: "utf8" })
  expect(identity.status).not.toBe(0)
  expect(identity.stderr).toContain("invalid agent")
  run(["setup", "empty", "reader"])
  const empty = spawnSync("python3", [helper, "send", "empty", "writer", "--stdin"], {
    env, input: " \n", encoding: "utf8",
  })
  expect(empty.status).not.toBe(0)
  expect(run(["history", "empty", "reader"])).toBe("")
})

test("malformed records are skipped while later valid messages remain readable", () => {
  run(["setup", "malformed", "reader"])
  appendFileSync(join(temporary, "malformed.ndjson"), 'not-json\n{"from":42,"text":"invalid"}\n')
  run(["send", "malformed", "writer", "valid"])
  expect(run(["poll", "malformed", "reader"]).trim()).toBe("[writer] valid")
  expect(JSON.parse(run(["status", "malformed", "reader"])).pending_lines).toBe(0)
})

test("leaving preserves history and the peer can still receive the departure", () => {
  run(["setup", "leaving", "proposer"])
  run(["setup", "leaving", "reviewer"])
  run(["send", "leaving", "proposer", "keep this"])
  run(["leave", "leaving", "proposer"])
  expect(run(["poll", "leaving", "reviewer"]).trim())
    .toBe("[proposer] keep this\n[proposer] left the channel")
  expect(run(["history", "leaving", "proposer"])).toContain("keep this")
})
