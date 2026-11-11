// Figures for /visualizaciones/democracia/, computed from the published JSON only (shared by the page, its metadata
// and the node test). No number in the copy is typed by hand.

export const PEER_CODES = ["DEU", "FRA", "ITA", "PRT"];
const ATTRIBUTABLE = new Set(["incumplimiento_declarado", "tension", "plazo_vencido"]);

export function partyOf(governments, id) {
  return governments.find((g) => g.id === id)?.party ?? null;
}

function yearsBetween(a, b) {
  return (Date.parse(b) - Date.parse(a)) / (365.25 * 86400000);
}

export function democracyModel(data) {
  const sgs = data.safeguards.filter((s) => s.classification);
  const byClass = { tercero_a_tiempo: [], tercero_tarde: [], buena_voluntad: [] };
  for (const s of sgs) byClass[s.classification]?.push(s);

  // Peers: for each Spanish goodwill safeguard, how many of the four peers have a third party (in time or late).
  const goodwillPeerFix = byClass.buena_voluntad.map((s) => ({
    id: s.id,
    name: s.name,
    peersWithThirdParty: PEER_CODES.filter((c) => ["tercero_a_tiempo", "tercero_tarde"].includes(s.peers[c]?.classification)).length,
  }));
  const goodwillWherePeersMostlyFix = goodwillPeerFix.filter((r) => r.peersWithThirdParty >= 3).length;
  const peerCells = byClass.buena_voluntad.flatMap((s) => PEER_CODES.map((c) => s.peers[c]?.classification));
  const peerWithData = peerCells.filter((c) => c && c !== "no_signal" && c !== "no_aplica").length;
  const peerThirdParty = peerCells.filter((c) => c === "tercero_a_tiempo" || c === "tercero_tarde").length;
  const goodwillWithAnyPeerFix = goodwillPeerFix.filter((r) => r.peersWithThirdParty >= 1).length;
  const peerClassCounts = Object.fromEntries(
    PEER_CODES.map((c) => [c, sgs.reduce((acc, s) => ({ ...acc, [s.peers[c]?.classification]: (acc[s.peers[c]?.classification] || 0) + 1 }), {})]),
  );

  // «Solo un lado lo hace»: episodes attributable to a government, by party, and per ten years in office.
  const snapshot = data.snapshot_date;
  const yearsInOffice = {};
  for (const g of data.governments) {
    const start = g.start < "1979-01-01" ? "1979-01-01" : g.start;
    yearsInOffice[g.party] = (yearsInOffice[g.party] || 0) + yearsBetween(start, g.end || snapshot);
  }
  const episodes = sgs.flatMap((s) => s.episodes.map((e) => ({ ...e, safeguard: s.id })));
  const attributed = episodes.filter((e) => ATTRIBUTABLE.has(e.kind) && e.power_holder?.government);
  const byParty = {};
  for (const e of attributed) {
    const p = partyOf(data.governments, e.power_holder.government);
    byParty[p] = byParty[p] || { party: p, episodes: 0, declared: 0, safeguards: new Set(), bySg: {} };
    byParty[p].bySg[e.safeguard] = (byParty[p].bySg[e.safeguard] || 0) + 1;
    byParty[p].episodes += 1;
    if (e.kind === "incumplimiento_declarado") byParty[p].declared += 1;
    byParty[p].safeguards.add(e.safeguard);
  }
  const partyRows = Object.values(byParty)
    .map((r) => ({
      party: r.party,
      episodes: r.episodes,
      declared: r.declared,
      safeguards: r.safeguards.size,
      years: Math.round(yearsInOffice[r.party] * 10) / 10,
      per10: Math.round((r.episodes / yearsInOffice[r.party]) * 100) / 10,
      decreeLaws: r.bySg.decretos_ley || 0,
    }))
    .sort((a, b) => b.episodes - a.episodes);
  const recent = attributed.filter((e) => e.start >= "2004-01-01").length;
  const reinforced = episodes.filter((e) => (e.power_holder?.indispensable_parties || []).length > 1).length;

  // Expired mandates: the longest, and the total per body.
  const mandates = [...data.mandates].sort((a, b) => b.days_expired - a.days_expired);
  const longest = mandates[0] || null;

  // Budgets
  const b = data.budgets;
  const prorrogued = b.prorrogued_years;

  // Decree-laws: current vs earlier governments, rates per month (denominator first).
  const govs = data.decree_laws.governments;
  const current = govs.at(-1);
  const earlier = govs.slice(0, -1);
  const maxEarlierRate = Math.max(...earlier.map((g) => g.rdl_per_month));
  const lastFull = data.decree_laws.annual.filter((r) => r.year < data.decree_laws.partial_year);

  // V-Dem latest values
  const v = data.vdem;
  const lastOf = (key, code) => v.indices[key][code]?.at(-1)?.value ?? null;
  const atYear = (key, code, year) => v.indices[key][code]?.find((p) => p.year === year)?.value ?? null;
  const libdem = Object.fromEntries(Object.keys(v.indices.libdem).map((c) => [c, lastOf("libdem", c)]));
  const esPeak = v.indices.libdem.ESP.reduce((best, p) => (p.value > best.value ? p : best), v.indices.libdem.ESP[0]);

  // Freezer
  const fz = data.freezer;
  const bucket = (id) => fz.summary.find((r) => r.bucket === id) || { bills: 0, median_extensions: 0, still_in_amendments: 0 };

  // Delays
  const delays = [...data.tc_delays].sort((a, b) => a.days - b.days);
  const medianDelay = delays.length ? delays[Math.floor(delays.length / 2)].days : null;
  const maxDelay = Math.max(1, ...sgs.map((s) => s.remedy_delay?.days || 0));

  return {
    n: sgs.length,
    byClass,
    goodwillPeerFix,
    goodwillWherePeersMostlyFix,
    peerCellsGoodwill: peerCells.length,
    peerWithData,
    peerThirdParty,
    goodwillWithAnyPeerFix,
    peerClassCounts,
    partyRows,
    attributedCount: attributed.length,
    episodesCount: episodes.length,
    recent,
    reinforced,
    mandates,
    longest,
    prorrogued,
    budgetFirst: b.first,
    budgetLast: b.last,
    current,
    maxEarlierRate,
    lastFull,
    libdem,
    libdemYear: v.latest_year,
    esPeak,
    atYear,
    fz,
    bucket,
    delays,
    medianDelay,
    maxDelay,
  };
}

export function democracySeo(data) {
  const m = democracyModel(data);
  const title = `Separación de poderes en España: ${m.byClass.buena_voluntad.length} de ${m.n} salvaguardas, a la buena voluntad`;
  const description = `${m.byClass.buena_voluntad.length} de ${m.n} reglas que limitan al poder en España no tienen a nadie que las haga cumplir; ${m.byClass.tercero_tarde.length} se cumplen tarde. Con datos del BOE, el TC y V-Dem.`;
  return { title, description, path: "/visualizaciones/democracia/" };
}
