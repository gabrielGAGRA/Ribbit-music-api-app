// scripts/dev-server.mjs
// Ensure compatibility with Node.js versions slightly below Angular CLI 22 minor requirements (e.g. 24.4.0)
const [major, minor] = process.versions.node.split('.').map(Number);
if (major === 24 && minor < 15) {
  Object.defineProperty(process.versions, 'node', { value: '24.15.0', configurable: true });
}

process.argv = [process.argv[0], 'ng', 'serve', ...process.argv.slice(2)];
import('@angular/cli/bin/ng.js');
