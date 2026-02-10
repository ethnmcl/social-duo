const { execFileSync } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

const REPO_URL = "https://github.com/ethnmcl/social-duo.git";
const SUBDIR = "social-duo";
const HOME = os.homedir();
const BASE_DIR = path.join(HOME, ".social-duo");
const VENV_DIR = path.join(BASE_DIR, "venv");

function ensureDir(p) {
  if (!fs.existsSync(p)) {
    fs.mkdirSync(p, { recursive: true });
  }
}

function getPython() {
  return process.platform === "win32" ? "python" : "python3";
}

function venvBin() {
  return process.platform === "win32" ? path.join(VENV_DIR, "Scripts") : path.join(VENV_DIR, "bin");
}

function run(cmd, args) {
  execFileSync(cmd, args, { stdio: "inherit" });
}

function main() {
  ensureDir(BASE_DIR);

  const python = getPython();
  if (!fs.existsSync(VENV_DIR)) {
    run(python, ["-m", "venv", VENV_DIR]);
  }

  const binDir = venvBin();
  const pip = process.platform === "win32" ? path.join(binDir, "pip.exe") : path.join(binDir, "pip");

  // Install/upgrade from GitHub repo subdirectory
  run(pip, ["install", "--upgrade", `git+${REPO_URL}#subdirectory=${SUBDIR}`]);
}

main();
