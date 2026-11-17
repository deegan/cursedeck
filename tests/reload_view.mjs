import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
const source = fs.readFileSync(new URL('../src/reloadView.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, {compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2020}}).outputText;
const {showLoadedVersion} = await import('data:text/javascript;base64,' + Buffer.from(compiled).toString('base64'));
const wait = ms => new Promise(r => setTimeout(r, ms));

function fakeLoader(active, plugins) {
  const state = {active, plugins, switched: 0};
  return {state, loader: {deckyState: {
    publicState: () => ({activePlugin: state.active, plugins: state.plugins}),
    setActivePlugin(name) { state.switched++; state.active = state.plugins.find(p => p.name === name); },
  }}};
}

// Open page shows the old copy; the new one registers later and takes over the page.
const fresh = {};
const old = {name: 'CurseDeck', content: {}};
const updated = fakeLoader(old, [old]);
showLoadedVersion(fresh, updated.loader, 10, 1);
await wait(5);
assert.equal(updated.state.switched, 0);
updated.state.plugins = [{name: 'CurseDeck', content: fresh}];
await wait(20);
assert.equal(updated.state.switched, 1);
assert.equal(updated.state.active.content, fresh);

// Another plugin's page, or no open page, is left alone.
for (const active of [{name: 'Other', content: {}}, null]) {
  const other = fakeLoader(active, [{name: 'CurseDeck', content: fresh}]);
  showLoadedVersion(fresh, other.loader, 10, 1);
  assert.equal(other.state.switched, 0);
}

// Missing or changed Decky internals never throw.
showLoadedVersion(fresh, undefined, 3, 1);
showLoadedVersion(fresh, {deckyState: {publicState() { throw new Error('x'); }, setActivePlugin() {}}}, 3, 1);

// Stopping cancels the wait.
const stopped = fakeLoader(old, [old]);
const stop = showLoadedVersion(fresh, stopped.loader, 10, 1);
stop();
stopped.state.plugins = [{name: 'CurseDeck', content: fresh}];
await wait(20);
assert.equal(stopped.state.switched, 0);
console.log('Reload view tests passed.');
