import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
const source = fs.readFileSync(new URL('../src/installations.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, {compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2020}}).outputText;
const {editionLabel, installationOptions} = await import('data:text/javascript;base64,' + Buffer.from(compiled).toString('base64'));
assert.equal(editionLabel('/games/WoW/_retail_'), 'Retail');
assert.equal(editionLabel('/games/WoW/_classic_era_/'), 'Classic Era');
assert.equal(editionLabel('/games/WoW/_forever_'), 'Forever');
const item = path => ({path,label:'World of Warcraft',source:'Steam library'});
const first = '/internal/WoW/_retail_';
const second = '/sdcard/WoW/_retail_';
assert.deepEqual(installationOptions([item(first),item(second)], first), [
  {data:first,label:'Retail (1)'},{data:second,label:'Retail (2)'},
]);
assert.deepEqual(installationOptions([], first), [{data:first,label:'Retail · saved location'}]);
assert.deepEqual(installationOptions([item(first)], first), [{data:first,label:'Retail'}]);
assert.deepEqual(installationOptions([], ''), []);
console.log('Installation selector tests passed.');
