#!/usr/bin/env node

const fs = require("node:fs/promises");
const path = require("node:path");
const readline = require("node:readline/promises");
const { stdin, stdout } = require("node:process");

const TARGETS = [
  {
    key: "steam",
    label: "Steam",
    url: "https://steamcommunity.com/market/",
    domains: ["steamcommunity.com", "store.steampowered.com", "steamstatic.com"],
  },
  {
    key: "csfloat",
    label: "CSFloat",
    url: "https://csfloat.com/search",
    domains: ["csfloat.com"],
  },
  {
    key: "buff163",
    label: "Buff163",
    url: "https://buff.163.com/market/csgo",
    domains: ["buff.163.com", "163.com"],
  },
];

const OUTPUT_ENV_NAME = "AUTH_COOKIES_PATH";

function loadPlaywright() {
  try {
    return require("playwright");
  } catch {
    console.error("Missing dependency: playwright");
    console.error("Install it with: npm install playwright");
    process.exit(1);
  }
}

function cookieMatchesDomains(cookie, domains) {
  const domain = String(cookie.domain || "").replace(/^\./, "").toLowerCase();
  return domains.some((candidate) => {
    const normalized = candidate.toLowerCase();
    return domain === normalized || domain.endsWith(`.${normalized}`);
  });
}

function buildCookieHeader(cookies) {
  return cookies
    .filter((cookie) => cookie.name && cookie.value)
    .map((cookie) => `${cookie.name}=${cookie.value}`)
    .join("; ");
}

function resolveOutputPath() {
  const configuredPath = process.env[OUTPUT_ENV_NAME];
  if (configuredPath && configuredPath.trim()) {
    return path.resolve(configuredPath.trim());
  }
  return path.resolve("cookies.json");
}

async function ensureParentDirectory(filePath) {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
}

async function waitForManualLogin({ target, page, context, prompt }) {
  await page.goto(target.url, { waitUntil: "domcontentloaded" });

  while (true) {
    await prompt.question(
      `[${target.label}] Complete login in the browser, then press ENTER to validate cookies... `
    );

    const scopedCookies = await context.cookies([target.url]);
    const matched = scopedCookies.filter((cookie) =>
      cookieMatchesDomains(cookie, target.domains)
    );

    if (matched.length > 0) {
      console.log(
        `[${target.label}] Login detected (${matched.length} cookies for target domains).`
      );
      return matched;
    }

    console.log(
      `[${target.label}] No session cookies detected yet. Please complete login and try again.`
    );
  }
}

async function run() {
  const { chromium } = loadPlaywright();
  const browser = await chromium.launch({
    headless: false,
    slowMo: 80,
  });

  const context = await browser.newContext();
  const prompt = readline.createInterface({ input: stdin, output: stdout });

  try {
    const platformCookies = {};

    for (const target of TARGETS) {
      const page = await context.newPage();
      const matchedCookies = await waitForManualLogin({
        target,
        page,
        context,
        prompt,
      });
      platformCookies[target.key] = {
        label: target.label,
        login_url: target.url,
        domains: target.domains,
        cookies: matchedCookies,
      };
      await page.close();
    }

    const allCookies = await context.cookies();
    for (const target of TARGETS) {
      const merged = allCookies.filter((cookie) =>
        cookieMatchesDomains(cookie, target.domains)
      );
      platformCookies[target.key].cookies = merged;
    }

    const payload = {
      schema_version: 1,
      captured_at: new Date().toISOString(),
      output_path: resolveOutputPath(),
      platforms: platformCookies,
      cookie_headers: Object.fromEntries(
        TARGETS.map((target) => [
          target.key,
          buildCookieHeader(platformCookies[target.key].cookies),
        ])
      ),
    };

    const outputPath = resolveOutputPath();
    await ensureParentDirectory(outputPath);
    await fs.writeFile(outputPath, JSON.stringify(payload, null, 2), {
      encoding: "utf8",
      mode: 0o600,
    });

    console.log(`Authentication cookies saved to ${outputPath}`);
    console.log(
      "Use AUTH_COOKIES_PATH to relocate the file if you do not want it in the repository root."
    );
  } finally {
    prompt.close();
    await context.close();
    await browser.close();
  }
}

run().catch((error) => {
  console.error("setup_auth failed:", error);
  process.exit(1);
});
