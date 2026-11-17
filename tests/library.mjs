import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
const source = fs.readFileSync(new URL('../src/library.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, {compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2020}}).outputText;
const {keepChecked} = await import('data:text/javascript;base64,' + Buffer.from(compiled).toString('base64'));
const base = {version:'1', error:null, missing:false, update:null};
const previous = {unmanaged:[], matching:{matched:2, unmatched:[], modified:[]}, addons:[
  {...base, id:1, name:'Syndicator', fileId:10, update:'291', blocked:true, download:{fileName:'S.zip', page:'p1'}},
  {...base, id:2, name:'Baganator', fileId:20, update:'862', blocked:true, download:{fileName:'B.zip', page:'p2'}},
]};
const next = {unmanaged:[], addons:[{...base, id:1, name:'Syndicator', fileId:11}, {...base, id:2, name:'Baganator', fileId:20}]};
const merged = keepChecked(previous, next);
assert.equal(merged.addons[0].update, null, 'the installed addon loses its stale update');
assert.equal(merged.addons[0].blocked, true, 'but stays marked as CurseForge-only');
assert.deepEqual(merged.addons[1].download, {fileName:'B.zip', page:'p2'}, 'untouched addons keep their download info');
assert.equal(merged.matching.matched, 2);
console.log('Library merge tests passed.');
