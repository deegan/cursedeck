import { useEffect, useRef, useState } from 'react';
import { forgetAll, peek, remembered, usePersistentState } from './persistentState';
import { Installed, Library, keepChecked } from './library';
import { ButtonItem, DialogButton, DropdownItem, Navigation, PanelSection, PanelSectionRow, TextField, ToggleField, staticClasses } from '@decky/ui';
import { callable, definePlugin, toaster, openFilePicker, FileSelectionType } from '@decky/api';
import { PluginUpdate, requestPluginUpdate, deckyInstallerBridge } from './pluginUpdates';
import { editionFor, installationOptions } from './installations';
import { AddonCard } from './AddonCard';
import { deckyLoader, showLoadedVersion } from './reloadView';
import { FaBoxOpen } from 'react-icons/fa';

type Reply<T> = { ok: true; data: T } | { ok: false; error: string };
type Settings = { path: string; flavor: number; hasKey: boolean };
type Discovery = { installations: {path: string; label: string; source: string}[]; warnings: string[]; limited: boolean; scannedDirectories?: number };
type Edition = { id: number; name: string };
type Mod = { id: number; name: string; summary: string; logo?: string };
const handoffFailed = callable<[string], Reply<PluginUpdate>>('update_handoff_failed');
const updateStatus = callable<[], Reply<PluginUpdate>>('plugin_update_status');
const preparePluginUpdate = callable<[], Reply<PluginUpdate>>('prepare_plugin_update');
const checkPluginUpdate = callable<[boolean], Reply<PluginUpdate>>('check_plugin_update');
const setUpdateChecks = callable<[boolean], Reply<{automaticChecks: boolean}>>('set_update_checks');
const status = callable<[], Reply<Settings>>('status');
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

function syncSummary(checked: Library): string {
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
  return parts.join(' ');
}

function Content() {
  const [pluginUpdate, setPluginUpdate] = useState<PluginUpdate>();
  const [updateError, setUpdateError] = useState('');
  const [tab, setTab] = usePersistentState('tab', 'installed');
  const [settings, setSettings] = useState<Settings>();
  const [discovery, setDiscovery] = usePersistentState<Discovery | undefined>('discovery', undefined);
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
  const [keyStatus, setKeyStatus] = useState<{ok: boolean; text: string}>();
  function changeKey(value: string) { setKey(value); setTypes([]); setKeyStatus(undefined); }
  // Check the key with CurseForge as soon as there is one; its edition list is the proof it works.
  useEffect(() => {
    if (tab !== 'setup' || types.length) return;
    const typed = key.trim();
    if (typed ? typed.length < 20 : !settings?.hasKey) return;
    let active = true;
    const timer = setTimeout(() => {
      setKeyStatus({ok: true, text: 'Checking the key with CurseForge…'});
      unwrap(editions(typed)).then(found => {
        if (!active) return;
        setTypes(found);
        setKeyStatus(typed ? {ok: true, text: 'CurseForge accepted this key. It is saved when you sync.'} : undefined);
      }).catch(e => { if (active) setKeyStatus({ok: false, text: e instanceof Error ? e.message : String(e)}); });
    }, typed ? 600 : 0);
    return () => { active = false; clearTimeout(timer); };
  }, [tab, key, settings?.hasKey, types.length]);
  // Fill in the CurseForge edition when the installation folder makes it certain.
  useEffect(() => {
    if (path && types.length && !types.some(t => t.id === flavor)) setFlavor(editionFor(path, types));
  }, [path, types]);
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
      <DropdownItem label="CurseDeck" selectedOption={tab} disabled={!!busy}
        rgOptions={[{data:'installed',label:'My addons'},{data:'browse',label:'Find addons'},{data:'setup',label:'Setup'},{data:'updates',label:'Plugin updates'}]}
        onChange={(option) => {
          setTab(option.data);
          if (option.data === 'setup' && !discovery) {
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
    {tab === 'setup' && <>
    <PanelSection title="1. Find World of Warcraft">
      {button('Search for WoW installations', () => scanInstallations())}
      {button('Browse for the WoW folder', async () => {
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
        if (!found.installations.length) setNotice('No WoW found in that folder. Select the World of Warcraft folder or the SD card that contains it.');
      })}
      {discovery && <p>{discovery.installations.length
        ? `Found ${discovery.installations.length} installation${discovery.installations.length === 1 ? '' : 's'}.`
        : 'No installations found. Check that the SD card is inserted, or browse for the folder.'}</p>}
      {discovery?.warnings.map(warning => <p key={warning}>{warning}</p>)}
    </PanelSection>
    <PanelSection title="2. Pick your version">
      {choices.length ? <>
        <DropdownItem label="WoW version" selectedOption={path} strDefaultLabel="Choose a version"
          disabled={!!busy} rgOptions={choices} onChange={option => {setPath(option.data); setFlavor(0);}} />
        {path && <p style={{overflowWrap:'anywhere', fontSize:12, color:'#b8bfc9'}}>{path}</p>}
      </> : <p>Find your installation first.</p>}
    </PanelSection>
    <PanelSection title="3. Add your CurseForge API key">
      {settings?.hasKey
        ? <p>Your API key is saved.</p>
        : <>
          <p>Create a free key at console.curseforge.com under API keys. Save it in a text file on the Deck and load it here.</p>
          {button('Open console.curseforge.com', async () => Navigation.NavigateToExternalWeb('https://console.curseforge.com/'))}
        </>}
      {button(settings?.hasKey ? 'Replace key from a text file' : 'Load key from a text file', async () => {
        let selected;
        try {
          const start = await home().catch(() => '/home/deck');
          selected = await openFilePicker(FileSelectionType.FILE, start || '/home/deck', true, true, undefined, undefined, false, true);
        } catch (error) {
          if (String(error).toLowerCase().includes('cancel')) return;
          throw error;
        }
        if (!selected?.path && !selected?.realpath) return;
        changeKey(await unwrap(keyFromFile(selected.realpath || selected.path)));
      })}
      {!settings?.hasKey && <PanelSectionRow><TextField label="Or type the key" value={key} bIsPassword
        disabled={!!busy} onChange={(e) => changeKey(e.target.value)} /></PanelSectionRow>}
      {keyStatus && <p role="status" style={keyStatus.ok ? undefined : {color:'#ffb4a9', overflowWrap:'anywhere'}}>{keyStatus.text}</p>}
      {types.length > 0 && path && <DropdownItem label="CurseForge edition" selectedOption={flavor}
        strDefaultLabel="Choose the edition" disabled={!!busy}
        rgOptions={types.map(t => ({data:t.id,label:t.name}))} onChange={(option) => setFlavor(option.data)} />}
    </PanelSection>
    <PanelSection title={settings?.path && settings?.hasKey && settings?.flavor ? '4. Sync' : '4. First-time sync'}>
      <p>Saves your setup, recognises the addons you already have, and checks them for updates. Your addon files are not changed.</p>
      {button('Sync my addons', async () => {
        const saved = await unwrap(configure(path, flavor, key));
        setSettings(saved); setKey(''); setResults([]); setSearched(false);
        const checked = await unwrap(installed(true));
        setLibrary(checked); setTab('installed');
        setNotice(`Setup saved. ${syncSummary(checked)}`);
      }, !path || !flavor || (!key && !settings?.hasKey))}
    </PanelSection>
    </>}
    {tab === 'browse' && <PanelSection title="Find addons · CurseForge">
      <PanelSectionRow><TextField label="Addon name" value={query} disabled={!!busy}
        onChange={(e) => {setQuery(e.target.value); setOffset(0); setSearched(false); setResults([]);}} /></PanelSectionRow>
      {(!settings?.hasKey || !settings?.flavor) && <p>Finish Setup to search CurseForge.</p>}
      {button('Search', () => browse(0), !settings?.path || !settings?.hasKey || !settings?.flavor)}
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
      {library.path && <div style={{overflowWrap:'anywhere', fontSize:12, color:'#b8bfc9', marginBottom:4}}>{library.path}</div>}
      {button('Refresh installed addons', async () => setLibrary(await unwrap(installed(false))), !settings?.path)}
      {button('Check for updates', async () => {
        const checked = await unwrap(installed(true));
        setLibrary(checked);
        setNotice(syncSummary(checked));
      }, !settings?.path || !settings?.hasKey || !settings?.flavor)}
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
