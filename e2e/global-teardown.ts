import { spawn } from "node:child_process";
import { rmSync } from "node:fs";
import path from "node:path";

export default function globalTeardown(): void {
  const tmp = path.resolve(__dirname, ".tmp");
  try {
    rmSync(tmp, { recursive: true, force: true, maxRetries: 2, retryDelay: 100 });
    return;
  } catch {
    // Playwright may stop the web server after global teardown; on Windows the
    // open SQLite handle blocks deletion until the server process exits.
  }

  const script =
    "setTimeout(() => {" +
    "try { require('fs').rmSync(" +
    JSON.stringify(tmp) +
    ", { recursive: true, force: true, maxRetries: 10, retryDelay: 200 }); }" +
    "catch {}" +
    "}, 2000);";
  const child = spawn(process.execPath, ["-e", script], {
    detached: true,
    stdio: "ignore",
    windowsHide: true,
  });
  child.unref();
}
