'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { flushSync } from 'react-dom';
import { withBasePath } from '../path-utils.mjs';
import styles from './launch.module.css';
import { loadHistoryFile } from './history-files.mjs';
import { SearchSelect, DateRangeField } from './filter-controls';

const initial = { authority: '', supplier: '', start: '0001-01-01', end: '9999-12-31' };
const money = (cents) => new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(cents / 100);

export default function LaunchExplorer({ audit, release }) {
  const [rows, setRows] = useState([]);
  const [loadState, setLoadState] = useState('loading');
  const defaults = { ...initial, start: audit.decision_date_min, end: audit.decision_date_max };
  const [filters, setFilters] = useState(defaults);
  const [page, setPage] = useState(0);
  const [message, setMessage] = useState('');
  const [downloading, setDownloading] = useState(false);
  const [filterResetToken, setFilterResetToken] = useState(0);
  const resultsRef = useRef(null);
  const base = withBasePath(`/spending/launch/${release.release}/`);
  const authorities = useMemo(() => [...new Set(rows.map((row) => row.authority))].sort(), [rows]);
  const suppliers = useMemo(() => [...new Set(rows.map((row) => row.supplier))].sort(), [rows]);
  const filtered = useMemo(() => rows.filter((row) => (!filters.authority || row.authority === filters.authority)
    && (!filters.supplier || row.supplier === filters.supplier)
    && row.decision_date >= filters.start && row.decision_date <= filters.end), [rows, filters]);
  const total = filtered.reduce((sum, row) => sum + row.amount_cents, 0);
  const lastPage = Math.max(0, Math.ceil(filtered.length / 12) - 1);
  const currentPage = Math.min(page, lastPage);
  const visible = filtered.slice(currentPage * 12, (currentPage + 1) * 12);

  function animate(update) {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) { update(); return; }
    if (document.startViewTransition) { document.startViewTransition(() => flushSync(update)); return; }
    const node = resultsRef.current;
    const oldHeight = node?.getBoundingClientRect().height;
    flushSync(update);
    if (node) node.animate([
      { height: `${oldHeight}px`, opacity: 0.65 },
      { height: `${node.getBoundingClientRect().height}px`, opacity: 1 },
    ], { duration: 220, easing: 'ease-out' });
  }

  useEffect(() => {
    let active = true;
    loadHistoryFile(base, release, 'awards.json')
      .then(async (blob) => JSON.parse(await blob.text()))
      .then((loaded) => {
        if (!Array.isArray(loaded) || loaded.length !== release.rows
          || loaded.reduce((sum, row) => sum + row.amount_cents, 0) !== release.amount_cents) {
          throw new Error('El fichero no coincide con el release verificado.');
        }
        if (active) animate(() => { setRows(loaded); setLoadState('ready'); });
      })
      .catch(() => { if (active) setLoadState('error'); });
    return () => { active = false; };
  }, [base, release.amount_cents, release.rows]);

  useEffect(() => {
    function restore() {
      const params = new URLSearchParams(window.location.hash.slice(1));
      const next = { ...defaults };
      for (const key of Object.keys(initial)) if (params.has(key)) next[key] = params.get(key);
      for (const key of ['start', 'end']) {
        const date = new Date(`${next[key]}T12:00:00Z`);
        if (!/^\d{4}-\d{2}-\d{2}$/.test(next[key]) || Number.isNaN(date.getTime())
          || date.toISOString().slice(0, 10) !== next[key]) next[key] = defaults[key];
      }
      if (next.start > next.end) [next.start, next.end] = [next.end, next.start];
      animate(() => { setFilters(next); setPage(0); });
    }
    restore(); window.addEventListener('hashchange', restore);
    return () => window.removeEventListener('hashchange', restore);
  }, []);

  function change(key, value) {
    animate(() => { setFilters((prior) => ({ ...prior, [key]: value })); setPage(0); setMessage(''); });
  }

  async function share() {
    const url = new URL(window.location.href);
    url.hash = new URLSearchParams(filters).toString();
    window.history.replaceState(null, '', url);
    try { await navigator.clipboard.writeText(url.href); setMessage('Enlace copiado. Reproduce estos filtros.'); }
    catch { setMessage('Enlace listo en la barra de direcciones. Puedes copiarlo.'); }
  }

  async function downloadCapture(row) {
    try {
      const blob = await loadHistoryFile(base, release, row.capture_path);
      const bytes = await blob.arrayBuffer();
      const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), (n) => n.toString(16).padStart(2, '0')).join('');
      if (hash !== row.entry_sha256) throw new Error('Capture checksum mismatch');
      const url = URL.createObjectURL(new Blob([bytes], { type: 'application/xml' }));
      const link = document.createElement('a'); link.className = 'spending-capture-download';
      link.href = url; link.download = `${row.entry_sha256}.xml`; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch { setMessage('No se pudo descargar la captura. Vuelve a intentarlo.'); }
  }

  async function downloadPackage() {
    setDownloading(true);
    setMessage('Preparando la descarga completa…');
    try {
      const blob = await loadHistoryFile(base, release, 'placsp-launch.zip');
      const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', await blob.arrayBuffer())), (n) => n.toString(16).padStart(2, '0')).join('');
      if (hash !== release.archive_sha256) throw new Error('Archive checksum mismatch');
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.className = 'spending-package-download'; link.href = url; link.download = 'placsp-launch.zip'; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 60000);
      setMessage('Descarga completa verificada.');
    } catch { setMessage('No se pudo descargar el paquete completo. Vuelve a intentarlo.'); }
    finally { setDownloading(false); }
  }

  function downloadCsv() {
    if (!rows.length) return;
    const keys = Object.keys(rows[0]);
    const escape = (value) => `"${String(value ?? '').replaceAll('"', '""')}"`;
    const text = [keys.map(escape).join(','), ...filtered.map((row) => keys.map((key) => escape(row[key])).join(','))].join('\r\n') + '\r\n';
    const url = URL.createObjectURL(new Blob([text], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a'); link.className = 'spending-csv-download'; link.href = url; link.download = 'placsp-resultados.csv'; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return (
    <main className={`shell spending-launch ${styles.page}`}>
      <header className={`spending-launch__hero ${styles.hero}`}>
        <p className="spending-launch__status">PLACSP · Histórico disponible</p>
        <h1 className="spending-launch__title">¿A quién se adjudicó el dinero público?</h1>
        <p className="spending-launch__intro">Elige un órgano o proveedor. Consulta importes adjudicados, abre el expediente y comprueba el resultado con los mismos datos descargables.</p>
        <p className="spending-launch__scope"><strong className="spending-launch__scope-count">{release.rows.toLocaleString('es-ES')} resultados elegibles</strong>, con decisiones entre {audit.decision_date_min} y {audit.decision_date_max}. El calendario consulta todo el histórico disponible. Adjudicado sin impuestos; no equivale a pagado.</p>
        <nav className={`spending-launch__links ${styles.actions}`} aria-label="Datos y contribución">
          <button className="spending-launch__package" onClick={downloadPackage} disabled={downloading}>{downloading ? 'Preparando descarga…' : `Descargar datos y consultas · ${Math.ceil(release.archive_bytes / 1024 / 1024)} MB`}</button>
          <a className="spending-launch__guide" href="https://github.com/gsusI/vota-con-la-chola/blob/main/docs/examples/placsp-launch/README.md">Reproducir con Python</a>
          <a className="spending-launch__contribute" href="https://github.com/gsusI/vota-con-la-chola/blob/main/docs/community/placsp-launch-tasks.md">Aportar una mejora</a>
        </nav>
      </header>
      <section className={`spending-filters ${styles.filters}`} aria-labelledby="spending-filter-title">
        <h2 className="spending-filters__title" id="spending-filter-title">Explora todas las adjudicaciones disponibles</h2>
        <div className={`spending-filters__controls ${styles.controls}`}>
          <SearchSelect id="authority" label="Órgano de contratación" placeholder="Todos los órganos"
            values={authorities} value={filters.authority} disabled={loadState !== 'ready'} onChange={(value) => change('authority', value)} />
          <SearchSelect id="supplier" label="Proveedor" placeholder="Todos los proveedores"
            values={suppliers} value={filters.supplier} disabled={loadState !== 'ready'} onChange={(value) => change('supplier', value)} />
          <DateRangeField start={filters.start} end={filters.end} resetToken={filterResetToken} disabled={loadState !== 'ready'} onChange={(range) => animate(() => {
            setFilters((prior) => ({ ...prior, ...range })); setPage(0); setMessage('');
          })} />
        </div>
        <div className={`spending-filters__actions ${styles.actions}`}>
          <button className="spending-filters__reset" disabled={loadState !== 'ready'} onClick={() => animate(() => {
            setFilters(defaults); setFilterResetToken((prior) => prior + 1); setPage(0); setMessage('');
          })}>Restablecer</button>
          <button className="spending-filters__share" onClick={share}>Copiar enlace a este resultado</button>
          <button className="spending-filters__csv" disabled={loadState !== 'ready'} onClick={downloadCsv}>Descargar resultados CSV</button>
        </div>
        <p className={`spending-filters__message ${styles.message}`} role="status">{message || (loadState === 'loading' ? 'Cargando y verificando los resultados…' : loadState === 'error' ? 'No se pudieron cargar los resultados. Vuelve a intentarlo.' : 'Los filtros agrupan variantes tipográficas; cada resultado conserva la etiqueta literal de su fuente.')}</p>
      </section>
      <section ref={resultsRef} className={`spending-results ${styles.results}`} aria-labelledby="spending-results-title">
        <h2 className="spending-results__title" id="spending-results-title" aria-live="polite">{loadState === 'loading' ? 'Cargando resultados…' : loadState === 'error' ? 'Resultados no disponibles' : `${filtered.length.toLocaleString('es-ES')} ${filtered.length === 1 ? 'resultado' : 'resultados'} · ${money(total)} sin impuestos`}</h2>
        <p className="spending-results__unit">Suma de resultados de adjudicación del histórico filtrado. Un expediente puede contener varios resultados o lotes.</p>
        {loadState === 'ready' && filtered.length === 0 ? <p className={`spending-results__empty ${styles.empty}`}>No hay resultados disponibles para esos filtros. Nuestra cobertura de las fuentes es incompleta.</p> : null}
        <ol className={`spending-results__list ${styles.list}`}>
          {visible.map((row) => <li className={`spending-result ${styles.card}`} key={row.award_key}>
            <article className="spending-result__article">
              <p className="spending-result__date">{row.decision_date} · expediente {row.contract_id}{row.lot_id ? ` · lote ${row.lot_id}` : ' · lote no publicado'}</p>
              <h3 className="spending-result__title">{row.title}</h3>
              <p className={`spending-result__amount ${styles.amount}`}>{money(row.amount_cents)} sin impuestos</p>
              <dl className="spending-result__parties">
                <dt className="spending-result__authority-label">Órgano</dt><dd className="spending-result__authority">{row.authority_source_text} · {row.authority_id || 'identificador no publicado'}</dd>
                <dt className="spending-result__supplier-label">Proveedor</dt><dd className="spending-result__supplier">{row.supplier_source_text} · {row.supplier_id_scheme} {row.supplier_id || 'identificador no publicado'}</dd>
              </dl>
              <div className={`spending-result__links ${styles.actions}`}>
                <a className="spending-result__official" href={row.source_url}>Abrir expediente oficial</a>
                <button className="spending-result__capture" onClick={() => downloadCapture(row)}>Descargar captura XML</button>
              </div>
            </article>
          </li>)}
        </ol>
        <nav className={`spending-results__pagination ${styles.actions}`} aria-label="Páginas de resultados">
          <button className="spending-results__previous" disabled={currentPage === 0} onClick={() => animate(() => setPage(currentPage - 1))}>Anterior</button>
          <span className="spending-results__page">Página {currentPage + 1} de {lastPage + 1}</span>
          <button className="spending-results__next" disabled={currentPage === lastPage} onClick={() => animate(() => setPage(currentPage + 1))}>Siguiente</button>
        </nav>
      </section>
      <footer className={`spending-method ${styles.method}`}>
        <h2 className="spending-method__title">Qué puedes comprobar y qué falta</h2>
        <p className="spending-method__scope">Todas las adjudicaciones elegibles del histórico disponible, usando la última versión no ambigua dentro del corpus congelado. Incluye {audit.capture_entries.toLocaleString('es-ES')} capturas XML verificadas. No prueba pagos, ejecución, irregularidades ni cobertura completa de la contratación pública.</p>
        <p className="spending-method__dates">El manifest original etiqueta 31/03/2025; sus filas contienen capturas de 31/03/2025 y 30/06/2025. Release analítica: 19/08/2026. Ninguna de esas fechas convierte el corte en datos actuales.</p>
        <p className="spending-method__review">Revisión comunitaria pendiente: 0 personas externas han validado este recorrido; 0 reproducciones externas registradas.</p>
        <p className="spending-method__credit">Fuente: Plataforma de Contratación del Sector Público. Captura y transformación: Vota Con La Chola. Las variantes tipográficas convergen para filtrar y sumar; cada fila conserva el nombre literal de la fuente.</p>
        <div className={`spending-method__links ${styles.actions}`}><a className="spending-method__audit" href={`${base}audit.json`}>Selección y exclusiones</a><a className="spending-method__hashes" href={`${base}manifest.json`}>Hashes de todos los archivos</a><a className="spending-method__rights" href="https://github.com/gsusI/vota-con-la-chola/blob/main/docs/legal/data-rights.md">Derechos de reutilización</a></div>
        <p className="spending-method__checksum">SHA-256 del ZIP: <code className={`spending-method__hash ${styles.hash}`}>{release.archive_sha256}</code></p>
      </footer>
    </main>
  );
}
