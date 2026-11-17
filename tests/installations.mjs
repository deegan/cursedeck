import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
const source = fs.readFileSync(new URL('../src/installations.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, {compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2020}}).outputText;
const {editionFor, editionLabel, installationOptions} = await import('data:text/javascript;base64,' + Buffer.from(compiled).toString('base64'));
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
const editions = [{id:79434,name:'WoW Mists of Pandaria Classic'},{id:67408,name:'WoW Classic'},{id:517,name:'WoW Retail'},{id:88568,name:'WoW Forever'}];
assert.equal(editionFor('/run/media/deck/SD/World of Warcraft/_forever_', editions), 88568);
assert.equal(editionFor('/games/WoW/_retail_/', editions), 517);
assert.equal(editionFor('/games/WoW/_classic_era_', editions), 67408);
assert.equal(editionFor('/games/WoW/_classic_', editions), 0);
assert.equal(editionFor('/games/WoW/_ptr_', editions), 0);
assert.equal(editionFor('/games/WoW/_retail_', []), 0);
console.log('Installation selector tests passed.');
