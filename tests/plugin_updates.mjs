import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
const source = fs.readFileSync(new URL('../src/pluginUpdates.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, {compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2020}}).outputText;
const {requestPluginUpdate} = await import('data:text/javascript;base64,' + Buffer.from(compiled).toString('base64'));
const update = {available:true,version:'0.3.0',artifact:'https://github.com/deegan/cursedeck/releases/download/v0.3.0/CurseDeck.zip',sha256:'a'.repeat(64)};
let calls = [];
const bridge = {async call(...args) { calls.push(args); }};
await requestPluginUpdate(update, bridge);
assert.deepEqual(calls, [['utilities/install_plugin', update.artifact, 'CurseDeck', '0.3.0', update.sha256, 2]]);
await assert.rejects(requestPluginUpdate(update), /Decky version/);
for (const invalid of [{...update,artifact:'https://evil.invalid/a.zip'},{...update,sha256:''},{...update,available:false}]) {
  await assert.rejects(requestPluginUpdate(invalid, bridge), /valid CurseDeck release/);
}
assert.equal(calls.length, 1);
await assert.rejects(requestPluginUpdate(update, {call:async () => {throw new Error('connection lost');}}), /connection lost/);
console.log('Plugin updater bridge tests passed.');
