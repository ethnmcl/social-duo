#!/usr/bin/env node
const { spawnSync } = require("child_process");
const os = require("os");
const path = require("path");
const fs = require("fs");

const HOME = os.homedir();
const BASE_DIR = path.join(HOME, ".social-duo");
const VENV_DIR = path.join(BASE_DIR, "venv");

function venvBin() {
  return process.platform === "win32" ? path.join(VENV_DIR, "Scripts") : path.join(VENV_DIR, "bin");
}

function main() {
  const binDir = venvBin();
  const exe = process.platform === "win32" ? "social_duo.exe" : "social_duo";
  const cli = path.join(binDir, exe);

  if (!fs.existsSync(cli)) {
    console.error("social-duo is not installed. Try reinstalling the npm package.");
    process.exit(1);
  }

  const args = process.argv.slice(2);
  const result = spawnSync(cli, args, { stdio: "inherit" });
  process.exit(result.status ?? 0);
}

main();
