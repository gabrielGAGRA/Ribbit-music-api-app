import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const EXPECTED_FLOWS = [
  '01-onboarding-discovery-swipe',
  '02-contextual-playlists-and-queue',
  '03-collaborative-jam-pond',
  '04-explore-search-and-community-reviews',
  '05-admin-console-governance-and-moderation',
];

function collectVideosFromSuites(suites, outMap) {
  for (const suite of suites ?? []) {
    for (const spec of suite.specs ?? []) {
      const flowStem = path.basename(spec.file ?? suite.file ?? '', '.e2e.ts');
      for (const testItem of spec.tests ?? []) {
        for (const result of testItem.results ?? []) {
          const videoAttachment = (result.attachments ?? []).find(
            (att) => att.name === 'video' && att.path,
          );
          if (videoAttachment && flowStem) {
            outMap.set(flowStem, videoAttachment.path);
          }
        }
      }
    }
    collectVideosFromSuites(suite.suites, outMap);
  }
}

const rootDir = process.cwd();
const testResultsDir = path.join(rootDir, 'test-results');
const resultsJsonPath = path.join(testResultsDir, 'results.json');
const outputVideosDir = path.join(rootDir, 'docs', 'videos');

fs.rmSync(testResultsDir, { recursive: true, force: true });
fs.mkdirSync(outputVideosDir, { recursive: true });

const extraArgs = process.argv.slice(2);
const playwrightCli = path.join(rootDir, 'node_modules', '@playwright', 'test', 'cli.js');
const runResult = spawnSync(process.execPath, [playwrightCli, 'test', ...extraArgs], {
  cwd: rootDir,
  stdio: 'inherit',
});

if (runResult.status !== 0) {
  process.exit(runResult.status ?? 1);
}

if (!fs.existsSync(resultsJsonPath)) {
  console.error(`Playwright JSON report not found at ${resultsJsonPath}`);
  process.exit(1);
}

const report = JSON.parse(fs.readFileSync(resultsJsonPath, 'utf-8'));
const videoByFlow = new Map();
collectVideosFromSuites(report.suites, videoByFlow);

const missing = [];
for (const flowName of EXPECTED_FLOWS) {
  const videoSrc = videoByFlow.get(flowName);
  if (!videoSrc || !fs.existsSync(videoSrc)) {
    missing.push(flowName);
    continue;
  }

  const videoDest = path.join(outputVideosDir, `${flowName}.webm`);
  fs.copyFileSync(videoSrc, videoDest);
  const stats = fs.statSync(videoDest);
  if (stats.size === 0) {
    missing.push(flowName);
    continue;
  }
  console.log(`[e2e-video] ${path.relative(rootDir, videoDest)} (${stats.size} bytes)`);
}

if (missing.length > 0) {
  console.error(`Missing or empty E2E videos for flows: ${missing.join(', ')}`);
  process.exit(1);
}
