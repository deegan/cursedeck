import { useEffect, useRef, useState } from 'react';
import { forgetAll, peek, remembered, usePersistentState } from './persistentState';
import { Installed, Library, keepChecked } from './library';
import { ButtonItem, DialogButton, DropdownItem, Navigation, PanelSection, PanelSectionRow, TextField, ToggleField, staticClasses } from '@decky/ui';
import { callable, definePlugin, toaster, openFilePicker, FileSelectionType } from '@decky/api';
import { PluginUpdate, requestPluginUpdate, deckyInstallerBridge } from './pluginUpdates';
import { installationOptions } from './installations';
import { AddonCard } from './AddonCard';
import { deckyLoader, showLoadedVersion } from './reloadView';
import { FaBoxOpen } from 'react-icons/fa';

type Reply<T> = { ok: true; data: T } | { ok: false; error: string };
type Settings = { path: string; flavor: number; hasKey: boolean; demo: boolean };
type Discovery = { installations: {path: string; label: string; source: string}[]; warnings: string[]; limited: boolean; scannedDirectories?: number };
type Edition = { id: number; name: string };
type Mod = { id: number; name: string; summary: string; logo?: string };
const handoffFailed = callable<[string], Reply<PluginUpdate>>('update_handoff_failed');
const updateStatus = callable<[], Reply<PluginUpdate>>('plugin_update_status');
const preparePluginUpdate = callable<[], Reply<PluginUpdate>>('prepare_plugin_update');
const checkPluginUpdate = callable<[boolean], Reply<PluginUpdate>>('check_plugin_update');
const setUpdateChecks = callable<[boolean], Reply<{automaticChecks: boolean}>>('set_update_checks');
const setDemo = callable<[boolean], Reply<Settings>>('set_demo');
const status = callable<[], Reply<Settings>>('status');
const configureLocal = callable<[string], Reply<Settings>>('configure_local');
const configure = callable<[string, number, string], Reply<Settings>>('configure');
const discoverIn = callable<[string], Reply<Discovery>>('discover');
const discover = callable<[], Reply<Discovery>>('discover');
const keyFromFile = callable<[string], Reply<string>>('key_from_file');
const home = callable<[], string>('home');
const editions = callable<[string], Reply<Edition[]>>('editions');
const search = callable<[string, number], Reply<Mod[]>>('search');
const installed = callable<[boolean], Reply<Library>>('installed');
const install = callable<[number], Reply<Library>>('install');
const installDownload = callable<[number, string], Reply<Library>>('install_download');
async function unwrap<T>(promise: Promise<Reply<T>>): Promise<T> {
  const reply = await promise;
  if (!reply.ok) throw new Error(reply.error);
  return reply.data;
}

function Content() {
  const [pluginUpdate, setPluginUpdate] = useState<PluginUpdate>();
  const [updateError, setUpdateError] = useState('');
  const [tab, setTab] = usePersistentState('tab', 'installed');
  const [settings, setSettings] = useState<Settings>();
  const [discovery, setDiscovery] = usePersistentState<Discovery | undefined>('discovery', undefined);
  const [manualPath, setManualPath] = usePersistentState('manualPath', false);
  const [path, setPath] = usePersistentState('path', '');
  const [key, setKey] = usePersistentState('key', '');
  const [flavor, setFlavor] = usePersistentState('flavor', 0);
  const [types, setTypes] = usePersistentState<Edition[]>('types', []);
  const [query, setQuery] = usePersistentState('query', '');
  const [results, setResults] = usePersistentState<Mod[]>('results', []);
  const [offset, setOffset] = usePersistentState('offset', 0);
  const [searched, setSearched] = usePersistentState('searched', false);
  const [library, setLibrary] = usePersistentState<Library>('library', { addons: [], unmanaged: [] });
  const running = useRef(false);
  const [busy, setBusy] = usePersistentState('busy', '');
  const [error, setError] = usePersistentState('error', '');
  const [notice, setNotice] = usePersistentState('notice', '');
  async function run(label: string, action: () => Promise<void>) {
    if (running.current) return;
    running.current = true;
    setBusy(label); setError(''); setNotice('');
    try { await action(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { running.current = false; setBusy(''); }
  }
  useEffect(() => {
    let active = true;
    void unwrap(updateStatus()).then(result => {
      if (active) setPluginUpdate(result);
      return unwrap(checkPluginUpdate(false));
    }).then(result => {
      if (active) setPluginUpdate(result);
    }).catch(error => { if (active) setUpdateError(String(error)); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    void run('Loading…', async () => {
      const saved = await unwrap(status());
      setSettings(saved);
      // Decky rebuilds this panel whenever Quick Access reopens; keep unsaved Setup choices.
      if (!remembered('path')) { setPath(saved.path); setFlavor(saved.flavor); }
      if (saved.path) setLibrary(await unwrap(installed(false)));
      else if (!remembered('tab')) { setTab('setup'); await scanInstallations(saved.path); }
    });
  }, []);
  const button = (label: string, action: () => Promise<void>, disabled = false) => (
    <PanelSectionRow><ButtonItem layout="below" disabled={!!busy || disabled}
      onClick={() => void run(label + '…', action)}>{label}</ButtonItem></PanelSectionRow>
  );
  async function scanInstallations(preferredPath = path) {
    const found = await unwrap(discover());
    setDiscovery(found);
    if (!preferredPath && found.installations.length === 1) {
      setPath(found.installations[0].path); setFlavor(0);
    }
  }
  const choices = installationOptions(discovery?.installations ?? [], settings?.path ?? '');
  async function browse(index: number) {
    setResults(await unwrap(search(query, index))); setOffset(index); setSearched(true);
  }
  async function add(id: number) {
    const next = await unwrap(install(id));
    setLibrary(keepChecked(peek<Library>('library') ?? library, next)); setNotice('Addon and required dependencies installed.');
  }
  const addonAction = (label: string, id: number) => <DialogButton disabled={!!busy}
    style={{ width: '100%', minWidth: 0, padding: '6px 8px', fontSize: 13, boxSizing: 'border-box' }}
    onClick={() => void run(label + '…', () => add(id))}>{label}</DialogButton>;
  const smallButton = (label: string, action: () => Promise<void>) => <DialogButton disabled={!!busy}
    style={{ width: '100%', minWidth: 0, padding: '6px 8px', fontSize: 13, boxSizing: 'border-box', marginTop: 6 }}
    onClick={() => void run(label + '…', action)}>{label}</DialogButton>;
  async function installDownloaded(mod: Installed) {
    let selected;
    try {
      const start = await home().catch(() => '/home/deck');
      selected = await openFilePicker(FileSelectionType.FILE, `${start || '/home/deck'}/Downloads`, true, true, undefined, ['zip'], false, false);
    } catch (error) {
      if (String(error).toLowerCase().includes('cancel')) return;
      throw error;
    }
    if (!selected?.path && !selected?.realpath) return;
    const next = await unwrap(installDownload(mod.id, selected.realpath || selected.path));
    setLibrary(keepChecked(peek<Library>('library') ?? library, next));
    setNotice(`${mod.name} ${mod.update ?? ''} installed from the downloaded file.`);
  }
  return <>
    <PanelSection>
      {settings?.demo && <>
        <p role="status">Offline demo · these are sample addons, not your installed WoW addons.</p>
        {button('Leave demo and find my addons', async () => {
          const saved = await unwrap(setDemo(false));
          setSettings(saved); setPath(saved.path); setFlavor(saved.flavor);
          setKey(''); setManualPath(false); setTypes([]); setResults([]); setSearched(false); setOffset(0);
          setLibrary({addons:[],unmanaged:[]}); setTab('setup');
          await scanInstallations(saved.path);
          if (saved.path) setLibrary(await unwrap(installed(false)));
        })}
      </>}
      <DropdownItem label="CurseDeck" selectedOption={tab} disabled={!!busy}
        rgOptions={[{data:'installed',label:'My addons'},{data:'browse',label:'Find addons'},{data:'setup',label:'Setup'},{data:'updates',label:'Plugin updates'}]}
        onChange={(option) => {
          setTab(option.data);
          if (option.data === 'setup' && !settings?.demo && !discovery) {
            void run('Finding WoW installations…', () => scanInstallations());
          }
        }} />
      {pluginUpdate?.available && tab !== 'updates' && <p>CurseDeck {pluginUpdate.version} is available. Open Plugin updates to install.</p>}
      {busy && <p role="status">{busy}</p>}
      {error && <p role="alert" style={{color:'#ffb4a9',overflowWrap:'anywhere'}}>{error}</p>}
      {notice && <p role="status">{notice}</p>}
    </PanelSection>
    {tab === 'updates' && <PanelSection title="CurseDeck updates">
      <p>Installed: {pluginUpdate?.current ?? 'Loading…'}</p>
      <p>Updates download and install here through Decky. Confirm its installation dialog when prompted.</p>
      {updateError && <p role="alert">{updateError}</p>}
      {pluginUpdate?.lastAttempt && <p role="status">{pluginUpdate.lastAttempt.message}</p>}
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
        const prepared = await unwrap(preparePluginUpdate());
        setPluginUpdate(await unwrap(updateStatus()));
        try { await requestPluginUpdate(prepared, deckyInstallerBridge()); }
        catch (error) {
          const message = error instanceof Error ? error.message : String(error);
          setPluginUpdate(await unwrap(handoffFailed(message)));
          throw error;
        }
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
        setManualPath(false);
        if (!saved.demo) await scanInstallations(saved.path);
      })}
      {!settings?.demo && <>
      <p>Choose the version of WoW whose addons you want to view.</p>
      <DropdownItem label="WoW installation" selectedOption={path}
        strDefaultLabel={busy ? 'Finding installations…' : 'Choose an installation'} disabled={!!busy || manualPath}
        rgOptions={choices}
        onChange={option => {setPath(option.data); setFlavor(0);}} />
      {choices.length > 1 && path && <p style={{overflowWrap:'anywhere'}}>Location: {path}</p>}
      {button('Find WoW installations', () => scanInstallations())}
      {button('Browse SD card or game folder', async () => {
        let selected;
        try { selected = await openFilePicker(FileSelectionType.FOLDER, path || '/run/media', false, true); }
        catch (error) {
          if (String(error).toLowerCase().includes('cancel')) return;
          throw error;
        }
        if (!selected?.path && !selected?.realpath) return;
        const found = await unwrap(discoverIn(selected.realpath || selected.path));
        setDiscovery(found);
        if (found.installations.length === 1) { setPath(found.installations[0].path); setFlavor(0); }
        else if (found.installations.length > 1) { setPath(''); setFlavor(0); }
        if (!found.installations.length) setNotice('No WoW executable found in that folder. Select the World of Warcraft folder or the card containing it.');
      })}
      {discovery?.scannedDirectories !== undefined && <p>Checked {discovery.scannedDirectories} folders.</p>}
      {discovery && !discovery.installations.length && <p>No installations found. Check that your SD card is mounted, or use Browse SD card or game folder to select its location.</p>}
      {discovery?.warnings.map(warning => <p key={warning}>{warning}</p>)}
      <ToggleField label="Use a custom location" description="Advanced: for installations the scan cannot find."
        checked={manualPath} disabled={!!busy} onChange={enabled => {
          setManualPath(enabled);
          if (!enabled && !choices.some(choice => choice.data === path)) {
            setPath(settings?.path ?? ''); setFlavor(settings?.flavor ?? 0);
          }
        }} />
      {manualPath && <PanelSectionRow><TextField label="Custom WoW folder" value={path} disabled={!!busy}
        onChange={(e) => {setPath(e.target.value); setFlavor(0);}} /></PanelSectionRow>}
      {button('Show my addons', async () => {
        const saved = await unwrap(configureLocal(path));
        setSettings(saved); setPath(saved.path); setFlavor(saved.flavor);
        setResults([]); setSearched(false); setOffset(0);
        setLibrary(await unwrap(installed(false))); setTab('installed');
        setNotice('Local addon scan complete.');
      }, !path)}
      <p>An API key is only needed to search CurseForge, download addons, and check online updates. Create your own free key at console.curseforge.com: sign in, open API keys, and copy the key. Saving it in a text file is easier than typing it here.</p>
      {!settings?.hasKey && button('Open console.curseforge.com', async () => Navigation.NavigateToExternalWeb('https://console.curseforge.com/'))}
      <PanelSectionRow><TextField label={settings?.hasKey ? 'API key (saved; leave blank to keep)' : 'CurseForge API key'}
        value={key} bIsPassword disabled={!!busy} onChange={(e) => setKey(e.target.value)} /></PanelSectionRow>
      {button('Load API key from a text file', async () => {
        let selected;
        try {
          const start = await home().catch(() => '/home/deck');
          selected = await openFilePicker(FileSelectionType.FILE, start || '/home/deck', true, true, undefined, undefined, false, true);
        } catch (error) {
          if (String(error).toLowerCase().includes('cancel')) return;
          throw error;
        }
        if (!selected?.path && !selected?.realpath) return;
        setKey(await unwrap(keyFromFile(selected.realpath || selected.path)));
      })}
      {key && <p role="status">A key is entered but not saved yet. Load WoW editions, then Save setup to store it.</p>}
      <p>The file should contain the key and nothing else. The key is stored on this Deck and only sent to CurseForge.</p>
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
      {!settings?.demo && (!settings?.hasKey || !settings?.flavor) && <p>Save your CurseForge API key (free from console.curseforge.com) and select your WoW edition in Setup to search online. Existing addons can be viewed without a key in My addons.</p>}
      {button('Search', () => browse(0), !settings?.path || (!settings?.demo && (!settings?.hasKey || !settings?.flavor)))}
      {searched && !results.length && <p>No addons found for this search and edition.</p>}
      {results.length > 0 && <p style={{fontSize:12, color:'#b8bfc9'}}>Select an addon to show its description.</p>}
      {results.map(mod => <AddonCard key={mod.id} name={mod.name} icon={mod.logo || ''}
        action={addonAction(library.addons.some(a => a.id === mod.id) ? 'Update / repair' : 'Install', mod.id)}>
        {mod.summary || 'No description available.'}
      </AddonCard>)}
      {offset > 0 && button('Previous page', () => browse(offset - 20))}
      {results.length === 20 && button('Next page', () => browse(offset + 20))}
    </PanelSection>}
    {tab === 'installed' && <PanelSection title="My addons">
      <p>Stable releases for your selected edition. Close WoW before installing or updating.</p>
      {library.path && <p style={{overflowWrap:'anywhere'}}>Scanning: {library.path}</p>}
      {button('Refresh installed addons', async () => setLibrary(await unwrap(installed(false))), !settings?.path)}
      {button('Check for updates', async () => {
        const checked = await unwrap(installed(true));
        setLibrary(checked);
        const found = checked.addons.filter(a => a.update && !a.blocked).length;
        const blockedUpdates = checked.addons.filter(a => a.update && a.blocked).length;
        const failed = checked.addons.filter(a => a.error).length;
        const outside = checked.localAddons?.length ?? checked.unmanaged.length;
        const matched = checked.matching?.matched ?? 0;
        const parts = [];
        if (matched) parts.push(`Recognised ${matched} addon(s) on CurseForge.`);
        if (!checked.addons.length) parts.push('No addons could be checked.');
        else parts.push(`${found ? `${found} update(s) available` : 'Everything checked is up to date'} (${checked.addons.length} checked${failed ? `, ${failed} need attention` : ''}).`);
        if (blockedUpdates) parts.push(`${blockedUpdates} more can only be updated through the CurseForge app.`);
        if (outside) parts.push(`${outside} folder(s) were not recognised and cannot be updated here.`);
        setNotice(parts.join(' '));
      }, !settings?.path || (!settings?.demo && (!settings?.hasKey || !settings?.flavor)))}
      {button('Update all', async () => {
        const updates = library.addons.filter(a => a.update && !a.blocked);
        const failures: string[] = [];
        for (const mod of updates) {
          try { await unwrap(install(mod.id)); }
          catch (e) { failures.push(`${mod.name}: ${e instanceof Error ? e.message : String(e)}`); }
        }
        setLibrary(await unwrap(installed(true)));
        if (failures.length) throw new Error(failures.join('\n'));
        setNotice(`${updates.length} addon(s) updated.`);
      }, !library.addons.some(a => a.update && !a.blocked))}
      {!library.addons.length && !library.unmanaged.length && <p>{settings?.path ? 'No addon folders found in this installation. Check the scanned path or choose another WoW edition in Setup.' : 'Choose your WoW installation in Setup, then save the folder to list its addons.'}</p>}
      {(library.addons.length > 0 || (library.localAddons?.length ?? 0) > 0) &&
        <p style={{fontSize:12, color:'#b8bfc9'}}>Select an addon to show details.</p>}
      {library.addons.map(mod => <AddonCard key={mod.id} name={mod.name} icon={mod.logo || ''} version={mod.version}
        status={[mod.missing && 'Files missing', mod.error && 'Needs attention', mod.update && (mod.blocked ? 'Update in CurseForge app' : 'Update available')].filter(Boolean).join(' · ')}
        warning={mod.missing || !!mod.error}
        action={mod.update && !mod.blocked ? addonAction('Update', mod.id) : undefined}>
        <div>{mod.adopted ? 'Recognised on CurseForge; updates through CurseDeck replace its folders' : 'Managed by CurseDeck'}</div>
        {mod.update && <div style={{marginTop:6}}>Available: {mod.update}</div>}
        {mod.blocked && <div style={{marginTop:6}}>The author only allows downloads through CurseForge's own app or website, so CurseDeck cannot download it.</div>}
        {mod.blocked && mod.update && <>
          <div style={{marginTop:6}}>Download {mod.download?.fileName || 'the release'} from CurseForge, then choose it here. CurseDeck checks it is exactly that release before installing.</div>
          {mod.download?.page && <>
            <div style={{marginTop:6, overflowWrap:'anywhere', fontSize:12}}>{mod.download.page}</div>
            {smallButton('Open download page', async () => Navigation.NavigateToExternalWeb(mod.download!.page))}
          </>}
          {smallButton('Install downloaded ZIP', () => installDownloaded(mod))}
        </>}
        {mod.error && <div style={{marginTop:6, color:'#ffb4a9'}}>{mod.error}</div>}
        {!mod.update && !mod.blocked && <div style={{marginTop:8}}>{addonAction('Repair / reinstall', mod.id)}</div>}
      </AddonCard>)}
      {(library.localAddons ?? []).map(addon => <AddonCard key={addon.folder} name={addon.name} icon="" version={addon.version}
        status={addon.error ? 'Needs attention' : undefined} warning={!!addon.error}>
        <div>Installed outside CurseDeck</div>
        <div style={{marginTop:6}}>Folder: {addon.folder}</div>
        {addon.notes && <div style={{marginTop:6}}>{addon.notes}</div>}
        {addon.error && <div style={{marginTop:6, color:'#ffb4a9'}}>{addon.error}</div>}
      </AddonCard>)}
      {!!library.unmanaged.length && <p>{library.matching
        ? 'These folders do not match a CurseForge release, for example because files were changed or the addon comes from elsewhere. They are left untouched.'
        : 'Check for updates recognises addons installed another way and checks them too.'}</p>}
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
  const content = <Content />;
  const stopWaiting = showLoadedVersion(content, deckyLoader());
  return {
  name: 'CurseDeck', titleView: <div className={staticClasses.Title}>CurseDeck</div>,
  content, icon: <FaBoxOpen />,
  onDismount() { stopped = true; clearInterval(timer); stopWaiting(); forgetAll(); },
};
});
