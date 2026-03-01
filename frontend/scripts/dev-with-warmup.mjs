import { spawn } from "node:child_process";
import process from "node:process";

const DEFAULT_BASE_URL = "http://127.0.0.1:3000";
const ROUTES_TO_WARM = [
  "/",
  "/app",
  "/app/chat",
  "/app/graph",
  "/app/conversations",
  "/app/entities",
  "/app/schema",
  "/app/search",
];
const MAX_HEALTH_RETRIES = 120;
const HEALTH_RETRY_DELAY_MS = 500;

function resolveNextBin() {
  if (process.platform === "win32") {
    return "node_modules\\.bin\\next.cmd";
  }
  return "node_modules/.bin/next";
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForServer(baseUrl) {
  for (let attempt = 0; attempt < MAX_HEALTH_RETRIES; attempt += 1) {
    try {
      const response = await fetch(baseUrl, { redirect: "manual" });
      if (response.status >= 200 && response.status < 500) {
        return true;
      }
    } catch {
      // Server not ready yet.
    }
    await sleep(HEALTH_RETRY_DELAY_MS);
  }
  return false;
}

async function warmRoutes(baseUrl) {
  const warmTargets = ROUTES_TO_WARM.map((route) => `${baseUrl}${route}`);
  await Promise.allSettled(
    warmTargets.map(async (target) => {
      try {
        await fetch(target, {
          headers: {
            "x-librarian-dev-warmup": "1",
          },
          redirect: "manual",
        });
      } catch {
        // Ignore warmup misses to avoid impacting normal dev flow.
      }
    }),
  );
}

async function main() {
  const extraArgs = process.argv.slice(2);
  const baseUrl = process.env.DEV_WARMUP_BASE_URL || DEFAULT_BASE_URL;
  const nextBin = resolveNextBin();
  const child = spawn(nextBin, ["dev", "--turbo", ...extraArgs], {
    cwd: process.cwd(),
    stdio: "inherit",
    shell: process.platform === "win32",
    env: process.env,
  });

  let shuttingDown = false;
  const shutdown = () => {
    if (shuttingDown) {
      return;
    }
    shuttingDown = true;
    child.kill("SIGINT");
  };

  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);

  void (async () => {
    const ready = await waitForServer(baseUrl);
    if (ready) {
      await warmRoutes(baseUrl);
      process.stdout.write("\n[librarian] Dev route warmup complete.\n");
    } else {
      process.stdout.write(
        "\n[librarian] Dev warmup skipped (server not reachable at configured base URL).\n",
      );
    }
  })();

  child.on("exit", (code, signal) => {
    process.removeListener("SIGINT", shutdown);
    process.removeListener("SIGTERM", shutdown);
    if (signal) {
      process.kill(process.pid, signal);
      return;
    }
    process.exit(code ?? 0);
  });
}

await main();
