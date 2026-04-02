#!/usr/bin/env node

const fs = require("node:fs/promises");
const path = require("node:path");
const readline = require("node:readline/promises");
const { stdin, stdout } = require("node:process");

const DEFAULT_URLS = {
  steam: "https://steamcommunity.com/market/",
  csfloat: "https://csfloat.com/search",
  buff163: "https://buff.163.com/market/csgo",
};

function loadPlaywright() {
  try {
    return require("playwright");
  } catch {
    console.error("Missing dependency: playwright");
    console.error("Install it with: npm install playwright");
    process.exit(1);
  }
}

function parseArgs(argv) {
  const parsed = {
    platform: "steam",
    url: undefined,
    cookieFile: undefined,
  };

  for (let i = 0; i < argv.length; i += 1) {
    const current = argv[i];
    const next = argv[i + 1];

    if (current === "--platform" && next) {
      parsed.platform = next.trim().toLowerCase();
      i += 1;
      continue;
    }
    if (current === "--url" && next) {
      parsed.url = next.trim();
      i += 1;
      continue;
    }
    if (current === "--cookie-file" && next) {
      parsed.cookieFile = next.trim();
      i += 1;
      continue;
    }
  }

  return parsed;
}

function resolveCookiePath(explicitPath) {
  if (explicitPath && explicitPath.trim()) {
    return path.resolve(explicitPath.trim());
  }

  const envPath = process.env.AUTH_COOKIES_PATH;
  if (envPath && envPath.trim()) {
    return path.resolve(envPath.trim());
  }

  return path.resolve("cookies.json");
}

function resolvePlatformSection(payload, platform) {
  if (payload && typeof payload === "object") {
    if (payload.platforms && typeof payload.platforms === "object") {
      return payload.platforms[platform];
    }
    return payload[platform];
  }
  return undefined;
}

function normalizeCookies(cookieRecords) {
  const normalized = [];
  for (const cookie of cookieRecords) {
    if (!cookie || typeof cookie !== "object") {
      continue;
    }

    const name = typeof cookie.name === "string" ? cookie.name : "";
    const value = typeof cookie.value === "string" ? cookie.value : "";
    const domain = typeof cookie.domain === "string" ? cookie.domain : "";
    if (!name.trim() || !value || !domain.trim()) {
      continue;
    }

    const normalizedCookie = {
      name,
      value,
      domain,
      path: typeof cookie.path === "string" && cookie.path ? cookie.path : "/",
    };

    if (typeof cookie.secure === "boolean") {
      normalizedCookie.secure = cookie.secure;
    }
    if (typeof cookie.httpOnly === "boolean") {
      normalizedCookie.httpOnly = cookie.httpOnly;
    }
    if (typeof cookie.sameSite === "string" && cookie.sameSite) {
      normalizedCookie.sameSite = cookie.sameSite;
    }
    if (typeof cookie.expires === "number" && cookie.expires > 0) {
      normalizedCookie.expires = Math.floor(cookie.expires);
    }

    normalized.push(normalizedCookie);
  }
  return normalized;
}

async function run() {
  const { chromium } = loadPlaywright();
  const args = parseArgs(process.argv.slice(2));
  const targetUrl = args.url || DEFAULT_URLS[args.platform] || DEFAULT_URLS.steam;
  const cookiePath = resolveCookiePath(args.cookieFile);

  const payload = JSON.parse(await fs.readFile(cookiePath, "utf8"));
  const section = resolvePlatformSection(payload, args.platform);
  const cookieRecords = Array.isArray(section?.cookies) ? section.cookies : [];
  const cookies = normalizeCookies(cookieRecords);

  if (cookies.length === 0) {
    console.error(
      `No cookies found for platform '${args.platform}' in ${cookiePath}. ` +
        "Capture them first with: node setup_auth.js"
    );
    process.exit(1);
  }

  const browser = await chromium.launch({
    headless: false,
    slowMo: 80,
  });
  const context = await browser.newContext();

  try {
    await context.addCookies(cookies);

    const page = await context.newPage();
    await page.goto(targetUrl, { waitUntil: "domcontentloaded" });

    console.log(`Loaded ${cookies.length} cookies for platform '${args.platform}'.`);
    console.log(`Opened URL: ${targetUrl}`);
    console.log("If the session is still not authenticated, recapture cookies with setup_auth.js.");

    const prompt = readline.createInterface({ input: stdin, output: stdout });
    await prompt.question("Press ENTER to close browser... ");
    prompt.close();
  } finally {
    await context.close();
    await browser.close();
  }
}

run().catch((error) => {
  console.error("open_logged_browser failed:", error);
  process.exit(1);
});
