// Deterministic synthesizer: 10 ObjectARX 2027 research slices -> unified native-ARX operation catalog.
// Mechanical merge. Preserves every op row verbatim (op_id). Applies the 3 _AUDIT.md tier rulings.
// Run:  node _build_catalog.js
// Writes: ../../config/autocad_native_arx_operation_catalog.json
'use strict';
const fs = require('fs');
const path = require('path');

const DIR = __dirname + path.sep;
const OUT = path.join(__dirname, '..', '..', 'config', 'autocad_native_arx_operation_catalog.json');
const SLICES = [
  'arx-framework.md', 'acdb-core.md', 'entities-geometry-graphics.md', 'custom-objects.md',
  'reactors-overrules.md', 'editor-delta.md', 'constraints-associativity.md', 'brep-topology.md',
  'ui-customization.md', 'com-activex-opm.md'
];

const PIPE = String.fromCharCode(1);
function splitRow(l) {
  let s = l.replace(/\\\|/g, PIPE);
  s = s.replace(/^\s*\|/, '').replace(/\|\s*$/, '');
  return s.split('|').map(c => c.split(PIPE).join('|').trim());
}
const isSep = l => /^\s*\|[\s:|-]*-[\s:|-]*\|/.test(l) && l.indexOf('---') >= 0;
const isRow = l => /^\s*\|/.test(l);

// ---- extract every 9-col op-catalog row across all slices ----
const raw = [];
for (const s of SLICES) {
  const L = fs.readFileSync(DIR + s, 'utf8').split('\n');
  for (let i = 0; i < L.length - 1; i++) {
    if (isRow(L[i]) && isSep(L[i + 1])) {
      const h = splitRow(L[i]);
      if (h.length >= 9 && /op_id/i.test(h[0] || '')) {
        let j = i + 2;
        while (j < L.length && isRow(L[j]) && !isSep(L[j])) {
          const c = splitRow(L[j]);
          if (c.length >= 9) {
            let o = c[0].replace(/`/g, '').trim();
            const m = o.match(/^([a-z0-9_.]+)\s*(\(.*\))?$/i);
            const id = m ? m[1] : o;
            if (/^[a-z0-9_]+(\.[a-z0-9_]+)+$/i.test(id)) {
              raw.push({ id, api: c[1], tierRaw: c[2], what: c[3], persistedRaw: c[6], ctxRaw: c[7], citation: c[8], slice: s, line: j + 1 });
            }
          }
          j++;
        }
        i = j - 1;
      }
    }
  }
}

// ---- merge cross-slice op_id duplicates (preserve both source_slices) ----
const merged = new Map();
for (const r of raw) {
  if (!merged.has(r.id)) merged.set(r.id, { ...r, slices: [r.slice] });
  else {
    const e = merged.get(r.id);
    if (!e.slices.includes(r.slice)) e.slices.push(r.slice);
    // keep the longer 'what' summary; prefer a native_arx tier if either says so
    if ((r.what || '').length > (e.what || '').length) e.what = r.what;
  }
}

// ---- tier normalization ----
const TIERS = ['native_arx_only', 'objectdbx_capable', 'managed_also', 'accoreconsole_lisp_also'];
function primaryTier(rawTier) {
  const low = rawTier.toLowerCase();
  let best = null, bi = 1e9;
  for (const t of TIERS) { const k = low.indexOf(t); if (k >= 0 && k < bi) { bi = k; best = t; } }
  return best || 'native_arx_only';
}
function normCtx(rawCtx) {
  const low = rawCtx.toLowerCase();
  if (/realdwg|standalone\s*\.?exe|standalone exe/.test(low)) return 'realdwg_standalone_out_of_scope';
  if (/hostless_dbx|host-less|hostless/.test(low)) return 'hostless_dbx_in_accoreconsole';
  if (/in_proc|in-proc|in_process/.test(low)) return 'in_process_host';
  if (/attended_app|attended/.test(low)) return 'host';
  if (/accoreconsole/.test(low)) return 'accoreconsole';
  if (/\bhost\b|host_session|either/.test(low)) return 'host';
  return rawCtx.replace(/`/g, '').trim() || 'host';
}
function normPersist(rawP) {
  const low = rawP.toLowerCase();
  if (/^\s*(yes|true|persisted)\b/.test(low)) return true;
  if (/^\s*(no|false|transient)\b/.test(low)) return false;
  if (low.indexOf('yes') >= 0 && low.indexOf('no') < 0) return true;
  if (low.indexOf('no') >= 0 && low.indexOf('yes') < 0) return false;
  return low.indexOf('yes') >= 0;
}

// ---- AUDIT _AUDIT.md rulings 2 & 3 (per-op tier overrides) ----
const OVR_MANAGED = new Set([
  // ruling 2: base + entity-level overrules => managed_also
  'overrule.global.enable', 'overrule.install', 'overrule.remove', 'overrule.query.has', 'overrule.applicable',
  'overrule.transform.install', 'overrule.geometry.install', 'overrule.grip.install', 'overrule.osnap.install',
  'overrule.visibility.install', 'overrule.highlight.install', 'overrule.highlightstate.install',
  'overrule.subentity.install', 'overrule.properties.install', 'overrule.drawable.install',
  // ruling 3: mainstream transient reactors (object/entity/database/editor/docmanager) => managed_also
  'react.editor.command_monitor', 'react.editor.sysvar_monitor', 'react.editor.lisp_monitor',
  'react.editor.dwg_lifecycle', 'react.editor.input_monitor', 'react.docmanager.attach', 'react.docmanager.monitor',
  'react.object.attach_transient', 'react.object.detach_transient', 'react.object.monitor',
  'react.entity.monitor', 'react.database.attach', 'react.database.monitor'
]);
const OVR_NATIVE = new Set([
  // ruling 2 keep native: object-lifecycle, queryX, dimstyle-overrule (authoring)
  'overrule.object.install', 'overrule.queryx.install', 'overrule.dimstyle.install',
  // ruling 3: low-level AcRxEventReactor native even though transient
  'react.rxevent.attach', 'react.rxevent.monitor'
]);
// ruling 1: side-DB DWG read/write already objectdbx_capable in slices; ctx normalized to hostless_dbx_in_accoreconsole.
// No standalone-exe op rows exist; realdwg boundary lives in prose, so no row needs the out-of-scope tag.

// ---- family assignment (slice-primary + keyword sub-routing) ----
function famOf(o) {
  const id = o.id, s = o.slice, a = (o.api + ' ' + o.what).toLowerCase();
  if (s === 'arx-framework.md') return 'runtime_commands';
  if (s === 'constraints-associativity.md') return 'constraints_associativity';
  if (s === 'brep-topology.md') return 'brep_solids';
  if (s === 'ui-customization.md') return 'ui_customization';
  if (s === 'com-activex-opm.md') return 'com_activex';
  if (s === 'custom-objects.md') return 'custom_objects_protocols';
  if (s === 'reactors-overrules.md') return id.startsWith('overrule.') ? 'custom_objects_protocols' : 'reactors_events';
  if (s === 'acdb-core.md') {
    if (/xrecord|xdata|dictionary|symbol|layer|linetype|dimstyle|textstyle|ucs|view|viewport|regapp|\bnod\b|extdict|\.table\b/.test(id + a)) return 'symbol_tables_dictionaries';
    if (/block|xref|clone|wblock|insert|attribute/.test(id + a)) return 'blocks_xrefs_clone';
    return 'objectdbx_database';
  }
  if (s === 'entities-geometry-graphics.md') {
    if (id.startsWith('compute.') || /acge|geometry kernel|\bcurve3d\b|\bplane\b|tolerance|intersect|matrix3d|vector3d|point3d/.test(a)) return 'geometry_kernel';
    if (id.startsWith('render.') || /acgi|worlddraw|viewportdraw|\btraits\b|transient graphic|highlight|grip|drawable/.test(a)) return 'graphics_system';
    return 'entities';
  }
  if (s === 'editor-delta.md') {
    if (/plot|layout|publish|pagesetup|page setup/.test(id + a)) return 'layouts_plot_publish';
    if (id.startsWith('command.register') || id.startsWith('command.unregister') || /regcmds|addcommand|command stack/.test(a)) return 'runtime_commands';
    if (id.startsWith('doc.') || /active document|syncopen|acedcommand|send command|live edit/.test(a)) return 'active_document_write_original';
    if (/palette|menu|ribbon|cui|statusbar|tray/.test(id)) return 'ui_customization';
    return 'editor_input';
  }
  return 'UNMAPPED';
}

function clampSummary(w) {
  // strip markdown, collapse to <= 14 words
  let t = (w || '').replace(/\*\*/g, '').replace(/`/g, '').replace(/\s+/g, ' ').trim();
  const words = t.split(' ');
  if (words.length > 14) t = words.slice(0, 14).join(' ');
  return t;
}

const MANAGED4 = new Set(['inspect.database.summary', 'write.layer.create', 'write.entity.line', 'write.xrecord.set']);

const operations = [];
for (const o of merged.values()) {
  let tier = primaryTier(o.tierRaw);
  let overridden = false;
  if (OVR_MANAGED.has(o.id) && tier !== 'managed_also') { tier = 'managed_also'; overridden = true; }
  else if (OVR_NATIVE.has(o.id) && tier !== 'native_arx_only') { tier = 'native_arx_only'; overridden = true; }
  operations.push({
    op_id: o.id,
    family: famOf(o),
    engine_tier: tier,
    dwg_persisted: normPersist(o.persistedRaw),
    execution_context: normCtx(o.ctxRaw),
    native_api: o.api.replace(/`/g, ''),
    summary: clampSummary(o.what),
    citation: o.citation.replace(/`/g, ''),
    source_slice: o.slices.length === 1 ? o.slices[0] : o.slices.join('+'),
    tier_overridden_by_audit: overridden,
    already_implemented_managed: MANAGED4.has(o.id)
  });
}

// inject the one managed op absent from native slices (inspect.database.summary) so all 4 existing managed ops are recorded
if (!operations.some(o => o.op_id === 'inspect.database.summary')) {
  operations.push({
    op_id: 'inspect.database.summary',
    family: 'objectdbx_database',
    engine_tier: 'managed_also',
    dwg_persisted: false,
    execution_context: 'hostless_dbx_in_accoreconsole',
    native_api: 'CadJobRunner.InspectDatabaseSummary (managed .NET; counts symbol tables + dicts)',
    summary: 'Summarize database: symbol-table + dictionary counts, units, modelspace entity count',
    citation: 'src/Ariadne.DwgGeometryExtractor/CadJobRunner.cs:47',
    source_slice: 'existing_managed_plane',
    tier_overridden_by_audit: false,
    already_implemented_managed: true
  });
}

// ---- sort by family then op_id ----
operations.sort((a, b) => a.family < b.family ? -1 : a.family > b.family ? 1 : (a.op_id < b.op_id ? -1 : a.op_id > b.op_id ? 1 : 0));

// ---- totals ----
const by_tier = { native_arx_only: 0, objectdbx_capable: 0, managed_also: 0, accoreconsole_lisp_also: 0 };
for (const o of operations) by_tier[o.engine_tier]++;
const by_family = {};
for (const o of operations) by_family[o.family] = (by_family[o.family] || 0) + 1;

const catalog = {
  schema: 'ariadne.autocad_native_arx_operation_catalog.v1',
  generated_at: '2026-06-18',
  source_slices: SLICES,
  totals: { ops: operations.length, by_tier, by_family },
  operations
};

fs.writeFileSync(OUT, JSON.stringify(catalog, null, 2) + '\n');
process.stdout.write('WROTE ' + OUT + '\n');
process.stdout.write('ops=' + operations.length + ' overrides=' + operations.filter(o => o.tier_overridden_by_audit).length + '\n');
process.stdout.write('by_tier=' + JSON.stringify(by_tier) + '\n');
process.stdout.write('already_implemented=' + operations.filter(o => o.already_implemented_managed).map(o => o.op_id).sort().join(',') + '\n');
process.stdout.write('unmapped=' + operations.filter(o => o.family === 'UNMAPPED').length + '\n');
