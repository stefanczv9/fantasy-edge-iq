const fs = require('fs');
const path = require('path');

const root = process.cwd();
const pub = path.join(root, 'public');
fs.rmSync(pub, { recursive: true, force: true });
fs.mkdirSync(pub, { recursive: true });

function ensureDir(p) { fs.mkdirSync(path.dirname(p), { recursive: true }); }
function copyIfExists(src, dst) {
  const from = path.join(root, src);
  const to = path.join(pub, dst);
  if (!fs.existsSync(from)) {
    console.log(`skip missing ${src}`);
    return;
  }
  ensureDir(to);
  fs.copyFileSync(from, to);
  console.log(`${src} -> public/${dst}`);
}

// Copy root static assets. Vercel will serve index.html at / and all direct assets.
for (const file of fs.readdirSync(root)) {
  if (!fs.statSync(path.join(root, file)).isFile()) continue;
  if (/\.(html|csv|xml|txt|png|svg|webmanifest)$/i.test(file)) {
    copyIfExists(file, file);
  }
}
try { fs.rmSync(path.join(pub, 'pricing.html'), { force: true }); } catch (_) {}

const routes = [
  ['euroleague-dashboard.html', 'euroleague/index.html'],
  ['euroleague-dashboard.html', 'euroleague/dashboard/index.html'],
  ['euroleague-team-analyzer.html', 'euroleague/team-analyzer/index.html'],
  ['euroleague-defense-vs-position.html', 'euroleague/defense-vs-position/index.html'],
  ['premier-league-dashboard.html', 'premier-league/index.html'],
  ['premier-league-dashboard.html', 'premier-league/dashboard/index.html'],
  ['premier-league-team-analyzer.html', 'premier-league/team-analyzer/index.html'],
  ['methodology.html', 'methodology/index.html'],
  ['about.html', 'about/index.html'],
  ['privacy.html', 'privacy/index.html'],
  ['terms.html', 'terms/index.html'],
  ['disclaimer.html', 'disclaimer/index.html'],
  ['sr-index.html', 'sr/index.html'],
  ['sr-euroleague.html', 'sr/euroleague/index.html'],
  ['sr-premier-league.html', 'sr/premier-league/index.html'],
  ['sr-about.html', 'sr/about/index.html'],
  ['sr-methodology.html', 'sr/methodology/index.html'],
  ['sr-privacy.html', 'sr/privacy/index.html'],
  ['sr-terms.html', 'sr/terms/index.html'],
  ['sr-disclaimer.html', 'sr/disclaimer/index.html'],
  ['el-index.html', 'el/index.html'],
  ['el-euroleague.html', 'el/euroleague/index.html'],
  ['el-premier-league.html', 'el/premier-league/index.html'],
  ['el-about.html', 'el/about/index.html'],
  ['el-methodology.html', 'el/methodology/index.html'],
  ['el-privacy.html', 'el/privacy/index.html'],
  ['el-terms.html', 'el/terms/index.html'],
  ['el-disclaimer.html', 'el/disclaimer/index.html'],
];
for (const [src, dst] of routes) copyIfExists(src, dst);
console.log('Build finished.');
