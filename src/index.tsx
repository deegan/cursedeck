import { useEffect, useRef, useState } from 'react';
import { ButtonItem, DropdownItem, PanelSection, PanelSectionRow, TextField, ToggleField, staticClasses } from '@decky/ui';
import { callable, definePlugin, toaster } from '@decky/api';
import { PluginUpdate, requestPluginUpdate, deckyInstallerBridge } from './pluginUpdates';
import { FaBoxOpen } from 'react-icons/fa';

type Reply<T> = { ok: true; data: T } | { ok: false; error: string };
type Settings = { path: string; flavor: number; hasKey: boolean; demo: boolean };
type Discovery = { installations: {path: string; label: string; source: string}[]; warnings: string[]; limited: boolean };
type Edition = { id: number; name: string };
type Mod = { id: number; name: string; summary: string };
type Installed = { id: number; name: string; version: string; update: string | null; error: string | null; missing: boolean };
type Library = { addons: Installed[]; unmanaged: string[] };
const checkPluginUpdate = callable<[boolean], Reply<PluginUpdate>>('check_plugin_update');
const setUpdateChecks = callable<[boolean], Reply<{automaticChecks: boolean}>>('set_update_checks');
const setDemo = callable<[boolean], Reply<Settings>>('set_demo');
const status = callable<[], Reply<Settings>>('status');
const configure = callable<[string, number, string], Reply<Settings>>('configure');
const discover = callable<[], Reply<Discovery>>('discover');
const editions = callable<[string], Reply<Edition[]>>('editions');
const search = callable<[string, number], Reply<Mod[]>>('search');
const installed = callable<[boolean], Reply<Library>>('installed');
const install = callable<[number], Reply<Library>>('install');
async function unwrap<T>(promise: Promise<Reply<T>>): Promise<T> {
  const reply = await promise;
  if (!reply.ok) throw new Error(reply.error);
  return reply.data;
}

function Content() {
  const [pluginUpdate, setPluginUpdate] = useState<PluginUpdate>();
  const [updateError, setUpdateError] = useState('');
  const [tab, setTab] = useState('installed');
  const [settings, setSettings] = useState<Settings>();
  const [discovery, setDiscovery] = useState<Discovery>();
  const [path, setPath] = useState('');
  const [key, setKey] = useState('');
  const [flavor, setFlavor] = useState(0);
  const [types, setTypes] = useState<Edition[]>([]);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Mod[]>([]);
  const [offset, setOffset] = useState(0);
  const [searched, setSearched] = useState(false);
  const [library, setLibrary] = useState<Library>({ addons: [], unmanaged: [] });
  const running = useRef(false);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  async function run(label: string, action: () => Promise<void>) {
    if (running.current) return;
    running.current = true;
    setBusy(label); setError(''); setNotice('');
    try { await action(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { running.current = false; setBusy(''); }
  }
  useEffect(() => {
    let active = true;
    void unwrap(checkPluginUpdate(false)).then(result => {
      if (active) setPluginUpdate(result);
    }).catch(error => { if (active) setUpdateError(String(error)); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    void run('Loading…', async () => {
      const saved = await unwrap(status());
      setSettings(saved); setPath(saved.path); setFlavor(saved.flavor);
      if (saved.path) setLibrary(await unwrap(installed(false)));
      else { setTab('setup'); setDiscovery(await unwrap(discover())); }
    });
  }, []);
  const button = (label: string, action: () => Promise<void>, disabled = false) => (
    <PanelSectionRow><ButtonItem layout="below" disabled={!!busy || disabled}
      onClick={() => void run(label + '…', action)}>{label}</ButtonItem></PanelSectionRow>
  );
  async function browse(index: number) {
    setResults(await unwrap(search(query, index))); setOffset(index); setSearched(true);
  }
  async function add(id: number) {
    setLibrary(await unwrap(install(id))); setNotice('Addon and required dependencies installed.');
  }
  return <>
    <PanelSection>
      {settings?.demo && <p role="status">Offline demo · sample addons in a temporary installation. Your WoW files are untouched.</p>}
      <DropdownItem label="CurseDeck" selectedOption={tab} disabled={!!busy}
        rgOptions={[{data:'installed',label:'My addons'},{data:'browse',label:'Find addons'},{data:'setup',label:'Setup'},{data:'updates',label:'Plugin updates'}]}
        onChange={(option) => setTab(option.data)} />
      {pluginUpdate?.available && tab !== 'updates' && <p>CurseDeck {pluginUpdate.version} is available. Open Plugin updates to install.</p>}
      {busy && <p role="status">{busy}</p>}
      {error && <p role="alert" style={{color:'#ffb4a9',overflowWrap:'anywhere'}}>{error}</p>}
      {notice && <p role="status">{notice}</p>}
    </PanelSection>
    {tab === 'updates' && <PanelSection title="CurseDeck updates">
      <p>Installed: {pluginUpdate?.current ?? 'Loading…'}</p>
      <p>Updates download and install here through Decky. Confirm its installation dialog when prompted.</p>
      {updateError && <p role="alert">{updateError}</p>}
      {pluginUpdate && <ToggleField label="Automatically check for releases"
        description="Check when Decky loads and every six hours while Steam is running."
        checked={pluginUpdate.automaticChecks} disabled={!!busy}
        onChange={enabled => void run('Saving update preference…', async () => {
          const prefs = await unwrap(setUpdateChecks(enabled));
          setPluginUpdate({...pluginUpdate, ...prefs});
        })} />}
      {button('Check for plugin update', async () => {
        const update = await unwrap(checkPluginUpdate(true));
        setPluginUpdate(update); setUpdateError('');
        if (!update.available) setNotice('You have the latest published CurseDeck release.');
      })}
      {pluginUpdate?.available && button(`Install CurseDeck ${pluginUpdate.version}`, async () => {
        await requestPluginUpdate(pluginUpdate, deckyInstallerBridge());
        setNotice('Confirm the update in Decky’s installation dialog.');
      })}
    </PanelSection>}
    {tab === 'setup'  && <PanelSection title="World of Warcraft setup">
      {button(settings?.demo ? 'Leave offline demo' : 'Try offline demo', async () => {
        const saved = await unwrap(setDemo(!settings?.demo));
        setSettings(saved); setPath(saved.path); setFlavor(saved.flavor); setKey('');
        setTypes([]); setResults([]); setOffset(0); setSearched(false);
        setLibrary(saved.path ? await unwrap(installed(false)) : {addons:[],unmanaged:[]});
        setTab(saved.demo ? 'installed' : 'setup');
      })}
      {!settings?.demo && <>
      {button('Find WoW installations', async () => setDiscovery(await unwrap(discover())))}
      {discovery && <>
        {discovery.installations.length > 0 ? <DropdownItem label="Detected installations"
          selectedOption={path} strDefaultLabel="Choose an installation" disabled={!!busy}
          rgOptions={discovery.installations.map(item => ({data:item.path,label:`${item.label} — ${item.path}`}))}
          onChange={option => {setPath(option.data); setFlavor(0);}} />
          : <p>No WoW installations found in Steam libraries. Enter the edition folder below if you installed it elsewhere.</p>}
        {discovery.warnings.map(warning => <p key={warning}>{warning}</p>)}
      </>}
      <p>Select the edition folder inside your WoW installation, for example _retail_ or _classic_. Close WoW before changing addons.</p>
      <PanelSectionRow><TextField label="WoW edition folder" value={path} disabled={!!busy}
        onChange={(e) => setPath(e.target.value)} /></PanelSectionRow>
      <PanelSectionRow><TextField label={settings?.hasKey ? 'API key (saved; leave blank to keep)' : 'CurseForge API key'}
        value={key} bIsPassword disabled={!!busy} onChange={(e) => setKey(e.target.value)} /></PanelSectionRow>
      <p>Use a key approved by CurseForge for third-party API access. It is stored locally and is never included in the plugin bundle.</p>
      {button('Load WoW editions', async () => setTypes(await unwrap(editions(key))))}
      {types.length > 0 && <DropdownItem label="WoW edition" selectedOption={flavor} disabled={!!busy}
        rgOptions={types.map(t => ({data:t.id,label:t.name}))} onChange={(option) => setFlavor(option.data)} />}
      {button('Save setup', async () => {
        const saved = await unwrap(configure(path, flavor, key));
        setSettings(saved); setKey(''); setResults([]); setSearched(false);
        setLibrary(await unwrap(installed(false))); setTab('installed'); setNotice('Setup saved.');
      }, !path || !flavor)}
      </>}
    </PanelSection>}
    {tab === 'browse' && <PanelSection title={settings?.demo ? 'Find addons · Offline demo' : 'Find addons · CurseForge'}>
      <PanelSectionRow><TextField label="Addon name" value={query} disabled={!!busy}
        onChange={(e) => {setQuery(e.target.value); setOffset(0); setSearched(false); setResults([]);}} /></PanelSectionRow>
      {button('Search', () => browse(0), !settings?.path)}
      {searched && !results.length && <p>No addons found for this search and edition.</p>}
      {results.map(mod => <PanelSection key={mod.id} title={mod.name}>
        <p>{mod.summary}</p>
        {button(library.addons.some(a => a.id === mod.id) ? 'Update / repair' : 'Install', () => add(mod.id))}
      </PanelSection>)}
      {offset > 0 && button('Previous page', () => browse(offset - 20))}
      {results.length === 20 && button('Next page', () => browse(offset + 20))}
    </PanelSection>}
    {tab === 'installed' && <PanelSection title="My addons">
      <p>Stable releases for your selected edition. Close WoW before installing or updating.</p>
      {button('Check for updates', async () => setLibrary(await unwrap(installed(true))), !settings?.path)}
      {button('Update all', async () => {
        const updates = library.addons.filter(a => a.update);
        const failures: string[] = [];
        for (const mod of updates) {
          try { await unwrap(install(mod.id)); }
          catch (e) { failures.push(`${mod.name}: ${e instanceof Error ? e.message : String(e)}`); }
        }
        setLibrary(await unwrap(installed(true)));
        if (failures.length) throw new Error(failures.join('\n'));
        setNotice(`${updates.length} addon(s) updated.`);
      }, !library.addons.some(a => a.update))}
      {!library.addons.length && <p>No addons managed yet. Use Find addons to install your first addon.</p>}
      {library.addons.map(mod => <PanelSection key={mod.id} title={mod.name}>
        <p>{mod.version}{mod.missing ? ' · Files missing' : ''}</p>
        {mod.update && <p>Available: {mod.update}</p>}
        {mod.error && <p>{mod.error}</p>}
        {button(mod.update ? 'Update' : 'Repair / reinstall', () => add(mod.id))}
      </PanelSection>)}
      {!!library.unmanaged.length && <PanelSection title="Existing unmanaged folders">
        <p>{library.unmanaged.join(', ')}</p>
        <p>These folders are left untouched. To manage one, back it up outside AddOns and install its project through Find addons. Your WTF settings are preserved.</p>
      </PanelSection>}
    </PanelSection>}
  </>;
}
export default definePlugin(() => {
  let stopped = false;
  let checking = false;
  let notifiedVersion: string | null = null;
  const check = async () => {
    if (checking) return;
    checking = true;
    try {
      const update = await unwrap(checkPluginUpdate(false));
      if (!stopped && update.automaticChecks && update.available && update.version !== notifiedVersion) {
        notifiedVersion = update.version;
        toaster.toast({title: 'CurseDeck update available', body: `Version ${update.version}. Open CurseDeck → Plugin updates to install.`});
      }
    } catch { /* Network failures remain available through the manual check button. */ }
    finally { checking = false; }
  };
  void check();
  const timer = setInterval(() => void check(), 6 * 60 * 60 * 1000);
  return {
  name: 'CurseDeck', titleView: <div className={staticClasses.Title}>CurseDeck</div>,
  content: <Content />, icon: <FaBoxOpen />,
  onDismount() { stopped = true; clearInterval(timer); },
};
});
