import { spawn } from "node:child_process";

const isWindows = process.platform === "win32";
const npm = isWindows ? "npm.cmd" : "npm";
const npx = isWindows ? "npx.cmd" : "npx";

function run(command, args, options = {}) {
  if (isWindows) {
    return spawn("cmd.exe", ["/d", "/s", "/c", command, ...args], { stdio: "inherit", shell: false, ...options });
  }
  return spawn(command, args, { stdio: "inherit", shell: false, ...options });
}

function spawnCommand(command, args, options = {}) {
  if (isWindows) {
    return spawn("cmd.exe", ["/d", "/s", "/c", command, ...args], { shell: false, ...options });
  }
  return spawn(command, args, { shell: false, ...options });
}

function waitForServer(url, timeoutMs = 60_000) {
  const started = Date.now();
  return new Promise((resolve, reject) => {
    const tick = async () => {
      try {
        const response = await fetch(url);
        if (response.ok) {
          resolve();
          return;
        }
      } catch {
        // Server not ready yet.
      }
      if (Date.now() - started > timeoutMs) {
        reject(new Error(`Timed out waiting for ${url}`));
        return;
      }
      setTimeout(tick, 500);
    };
    tick();
  });
}

function stop(child) {
  if (!child.pid || child.killed) return Promise.resolve();
  if (!isWindows) {
    child.kill("SIGTERM");
    return Promise.resolve();
  }
  return new Promise((resolve) => {
    const killer = spawn("taskkill", ["/pid", String(child.pid), "/t", "/f"], { stdio: "ignore" });
    const timer = setTimeout(resolve, 2_000);
    killer.on("exit", () => {
      clearTimeout(timer);
      resolve();
    });
    killer.on("error", () => {
      clearTimeout(timer);
      resolve();
    });
  });
}

const vite = run(npm, ["run", "dev", "--", "--host", "127.0.0.1", "--port", "5173", "--strictPort"]);
let exitCode = 1;

try {
  await waitForServer("http://127.0.0.1:5173");
  const result = await new Promise((resolve) => {
    const tests = spawnCommand(npx, ["playwright", "test", "--config", "playwright.config.ts"], { stdio: ["ignore", "pipe", "pipe"] });
    let output = "";
    const finish = async (code) => {
      await stop(tests);
      resolve(code);
    };
    tests.stdout.on("data", (chunk) => {
      const text = chunk.toString();
      output += text;
      process.stdout.write(text);
      if (/\b\d+\s+passed\b/.test(output)) void finish(0);
    });
    tests.stderr.on("data", (chunk) => {
      const text = chunk.toString();
      output += text;
      process.stderr.write(text);
    });
    tests.on("exit", (code) => resolve(code ?? 1));
    tests.on("error", () => resolve(1));
  });
  exitCode = Number(result);
} finally {
  await stop(vite);
  process.exit(exitCode);
}
