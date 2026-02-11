#!/usr/bin/env node
const { execFileSync, spawnSync } = require("child_process");
const os = require("os");
const path = require("path");
const fs = require("fs");

const HOME = os.homedir();
const BASE_DIR = path.join(HOME, ".social-duo");
const VENV_DIR = path.join(BASE_DIR, "venv");

function venvBin() {
  return process.platform === "win32" ? path.join(VENV_DIR, "Scripts") : path.join(VENV_DIR, "bin");
}

function runInstaller() {
  const installer = path.join(__dirname, "install.js");
  execFileSync(process.execPath, [installer], { stdio: "inherit" });
}

function parseDotEnv(content) {
  const out = {};
  for (const rawLine of content.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const idx = line.indexOf("=");
    if (idx < 0) continue;
    const key = line.slice(0, idx).trim();
    let value = line.slice(idx + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    if (key) out[key] = value;
  }
  return out;
}

function loadEnvFromFile(envPath) {
  if (!fs.existsSync(envPath)) return {};
  try {
    const content = fs.readFileSync(envPath, "utf8");
    return parseDotEnv(content);
  } catch {
    return {};
  }
}

function loadRuntimeEnv() {
  const cwdEnv = loadEnvFromFile(path.join(process.cwd(), ".env"));
  const workspaceEnv = loadEnvFromFile(path.join(BASE_DIR, ".env"));
  return { ...workspaceEnv, ...cwdEnv };
}

function main() {
  const binDir = venvBin();
  const exe = process.platform === "win32" ? "social_duo.exe" : "social_duo";
  const cli = path.join(binDir, exe);

  if (!fs.existsSync(cli)) {
    try {
      runInstaller();
    } catch {
      console.error("social-duo installation failed. Re-run `npm i social-duo`.");
      process.exit(1);
    }
    if (!fs.existsSync(cli)) {
      console.error("social-duo is not installed. Re-run `npm i social-duo`.");
      process.exit(1);
    }
  }

  const args = process.argv.slice(2);
  const dotenvVars = loadRuntimeEnv();
  const result = spawnSync(cli, args, {
    stdio: "inherit",
    env: { ...process.env, ...dotenvVars },
  });
  if (result.error) {
    console.error(`Failed to launch social-duo: ${result.error.message}`);
    process.exit(1);
  }
  process.exit(result.status ?? 0);
}

main();
