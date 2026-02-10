const { execFileSync } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

const REPO_URL = "https://github.com/ethnmcl/social-duo.git";
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

  // Install/upgrade from GitHub repo.
  const installTarget = `git+${REPO_URL}`;
  const installTargetWithSubdir = `git+${REPO_URL}#subdirectory=social-duo`;
  try {
    run(pip, ["install", "--upgrade", installTarget]);
  } catch (err) {
    // Backward-compatible fallback if project metadata lives in a subdirectory.
    try {
      run(pip, ["install", "--upgrade", installTargetWithSubdir]);
    } catch (fallbackErr) {
      console.error("[social-duo] Python install failed.");
      console.error(`[social-duo] Attempted: pip install --upgrade ${installTarget}`);
      console.error(`[social-duo] Fallback attempted: pip install --upgrade ${installTargetWithSubdir}`);
      console.error("[social-duo] Ensure python3, pip, and git are installed, then retry npm install.");
      process.exit(1);
    }
  }
}

main();
