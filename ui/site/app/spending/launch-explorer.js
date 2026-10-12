'use client';

import { useEffect, useRef, useState } from 'react';
import { flushSync } from 'react-dom';
import { withBasePath } from '../path-utils.mjs';
import styles from './launch.module.css';
import { loadHistoryFile } from './history-files.mjs';
import { queryUrl, searchOptions } from './backend.mjs';
import { SearchSelect, DateRangeField } from './filter-controls';

const initial = { authority: '', supplier: '', start: '0001-01-01', end: '9999-12-31', q: '', date_scope: 'all' };
const money = (cents) => new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(cents / 100);

export default function LaunchExplorer({ audit, release, apiVersion }) {
  const [result, setResult] = useState({rows:[],count:0,amount_cents:0,next_cursor:null});
  const [cursors, setCursors] = useState([0]);
  const [restored, setRestored] = useState(false);
  const [csvBusy, setCsvBusy] = useState(false);
  const [queryDraft, setQueryDraft] = useState('');
  const [loadState, setLoadState] = useState('loading');
  const defaults = { ...initial, start: audit.decision_date_min, end: audit.decision_date_max };
  const [filters, setFilters] = useState(defaults);
  const [page, setPage] = useState(0);
  const [message, setMessage] = useState('');
  const [downloading, setDownloading] = useState(false);
  const [filterResetToken, setFilterResetToken] = useState(0);
  const resultsRef = useRef(null);
  const base = withBasePath(`/spending/launch/${release.release}/`);
  const total = result.amount_cents;
  const lastPage = Math.max(0, Math.ceil(result.count / 12) - 1);
  const currentPage = page;
  const visible = loadState === 'ready' ? result.rows : [];
  const authoritySearch = (q, signal) => searchOptions('authority', q, signal, apiVersion);
  const supplierSearch = (q, signal) => searchOptions('supplier', q, signal, apiVersion);

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
    if (!restored) return;
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      animate(() => setLoadState('loading'));
      try {
        const response = await fetch(queryUrl('/v1/awards', { ...filters, after: cursors[page] || 0, limit: 12, version: apiVersion }), { signal: controller.signal });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'No se pudieron consultar los resultados.');
        if (data.release !== release.release) throw new Error('La versión de datos está cambiando. Recarga la página en unos segundos para consultar resultados y capturas de la misma versión.');
        if (data.rows.length > 12 || !Number.isSafeInteger(data.count)) throw new Error('Respuesta no válida.');
        if (!controller.signal.aborted) animate(() => { setResult(data); setLoadState('ready'); });
      } catch (error) {
        if (!controller.signal.aborted) animate(() => { setLoadState('error'); setMessage(error.message); });
      }
    }, 150);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [filters, page, restored]);

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
      if (!['all', 'dated', 'unresolved'].includes(next.date_scope)) next.date_scope = 'all';
      if (next.start > next.end) [next.start, next.end] = [next.end, next.start];
      animate(() => { setFilters(next); setQueryDraft(next.q); setPage(0); setCursors([0]); setRestored(true); });
    }
    restore(); window.addEventListener('hashchange', restore);
    return () => window.removeEventListener('hashchange', restore);
  }, []);

  function change(key, value) {
    animate(() => { setFilters((prior) => ({ ...prior, [key]: value })); setPage(0); setCursors([0]); setLoadState('loading'); setMessage(''); });
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

  async function downloadCsv() {
    setCsvBusy(true); setMessage('Descargando los resultados elegidos…');
    const selected = { ...filters };
    try {
      let after = 0;
      const chunks = [];
      do {
        const response = await fetch(queryUrl('/v1/export', { ...selected, after, limit: 200, version: result.version }));
        if (!response.ok) throw new Error('Exportación interrumpida. Vuelve a intentarlo; no se ha generado un CSV parcial.');
        chunks.push(await response.blob());
        const next = response.headers.get('X-Next-Cursor');
        if (next === '') break;
        const cursor = Number(next);
        if (!Number.isSafeInteger(cursor) || cursor <= after) throw new Error('Paginación de descarga no válida.');
        after = cursor;
      } while (after <= release.rows);
      const url = URL.createObjectURL(new Blob(chunks, { type: 'text/csv;charset=utf-8' }));
      const link = document.createElement('a'); link.className = 'spending-csv-download'; link.href = url; link.download = 'placsp-resultados.csv'; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 60000);
      setMessage('CSV descargado con los filtros seleccionados.');
    } catch (error) { setMessage(error.message); }
    finally { setCsvBusy(false); }
  }

  return (
    <main className={`shell spending-launch ${styles.page}`}>
      <header className={`spending-launch__hero ${styles.hero}`}>
        <p className="spending-launch__status">PLACSP · Histórico disponible</p>
        <h1 className="spending-launch__title">¿A quién se adjudicó el dinero público?</h1>
        <p className="spending-launch__intro">Elige un órgano o proveedor. Consulta importes adjudicados, abre el expediente y comprueba el resultado con los mismos datos descargables.</p>
        <p className="spending-launch__scope"><strong className="spending-launch__scope-count">{release.rows.toLocaleString('es-ES')} resultados elegibles</strong>, en el corpus adquirido de PLACSP. Cobertura parcial: publicaciones actualizadas en el primer semestre de 2025. El calendario filtra fechas de adjudicación; sus extremos no prueban continuidad histórica. Adjudicado sin impuestos; no equivale a pagado.</p>
        <nav id="spending-downloads" className={`spending-launch__links ${styles.actions}`} aria-label="Datos y contribución">
          <button className="spending-launch__package" onClick={downloadPackage} disabled={downloading}>{downloading ? 'Preparando descarga…' : `Descargar datos fuente y consultas · ${Math.ceil(release.archive_bytes / 1024 / 1024)} MB`}</button>
          <a className="spending-launch__guide" href="https://github.com/gsusI/vota-con-la-chola/blob/main/docs/examples/placsp-launch/README.md">Reproducir con Python</a>
          <a className="spending-launch__contribute" href="https://github.com/gsusI/vota-con-la-chola/blob/main/docs/community/placsp-launch-tasks.md">Aportar una mejora</a>
        </nav>
      </header>
      <section className={`spending-filters ${styles.filters}`} aria-labelledby="spending-filter-title">
        <h2 className="spending-filters__title" id="spending-filter-title">Explora todas las adjudicaciones disponibles</h2>
        <div className={`spending-filters__controls ${styles.controls}`}>
          <SearchSelect id="authority" label="Órgano de contratación" placeholder="Todos los órganos"
            loadOptions={authoritySearch} value={filters.authority} disabled={false} onChange={(value) => change('authority', value)} />
          <SearchSelect id="supplier" label="Proveedor" placeholder="Todos los proveedores"
            loadOptions={supplierSearch} value={filters.supplier} disabled={false} onChange={(value) => change('supplier', value)} />
          <DateRangeField start={filters.start} end={filters.end} resetToken={filterResetToken} disabled={filters.date_scope === 'unresolved'} onChange={(range) => animate(() => {
            setFilters((prior) => ({ ...prior, ...range })); setPage(0); setCursors([0]); setLoadState('loading'); setMessage('');
          })} />
        </div>
        <div className="spending-date-scope">
          <label className="spending-date-scope__label" htmlFor="spending-date-scope">Resultados con fecha dudosa</label>
          <select className="spending-date-scope__select" id="spending-date-scope" value={filters.date_scope} onChange={(event) => change('date_scope', event.target.value)} aria-describedby="spending-date-scope-help">
            <option className="spending-date-scope__option" value="all">Incluir junto al rango elegido</option>
            <option className="spending-date-scope__option" value="dated">Excluir: solo fechas del rango</option>
            <option className="spending-date-scope__option" value="unresolved">Ver solo fechas dudosas</option>
          </select>
          <p className="spending-date-scope__help" id="spending-date-scope-help">{filters.date_scope === 'unresolved' ? 'El calendario no se aplica. Se mantienen los filtros de órgano, proveedor y texto.' : filters.date_scope === 'dated' ? 'Solo resultados con fecha válida dentro del calendario.' : 'Las fechas dudosas no pueden situarse dentro del calendario. Se incluyen aparte y se identifican en cada resultado.'}</p>
        </div>
        <form className="spending-text-search" onSubmit={(event) => { event.preventDefault(); change('q', queryDraft.trim()); }}>
          <label className="spending-text-search__label" htmlFor="spending-query">Objeto del contrato o expediente</label>
          <input className="spending-text-search__input" id="spending-query" value={queryDraft} onChange={(event) => setQueryDraft(event.target.value)} minLength={2} maxLength={80} placeholder="Ej.: materiales hidráulicos" />
          <button className="spending-text-search__submit" type="submit">Buscar</button>
        </form>
        <div className={`spending-filters__actions ${styles.actions}`}>
          <button className="spending-filters__reset" disabled={false} onClick={() => animate(() => {
            setFilters(defaults); setQueryDraft(''); setFilterResetToken((prior) => prior + 1); setPage(0); setCursors([0]); setLoadState('loading'); setMessage('');
          })}>Restablecer</button>
          <button className="spending-filters__share" onClick={share}>Copiar enlace a este resultado</button>
          <button className="spending-filters__csv" disabled={loadState !== 'ready' || csvBusy} onClick={downloadCsv}>{csvBusy ? 'Descargando CSV…' : 'Descargar resultados CSV'}</button>
        </div>
        <p className={`spending-filters__message ${styles.message}`} role="status">{message || (loadState === 'loading' ? 'Consultando resultados…' : loadState === 'error' ? 'No se pudieron cargar los resultados. Vuelve a intentarlo.' : 'Los filtros agrupan variantes tipográficas; cada resultado conserva la etiqueta literal de su fuente.')}</p>
      </section>
      <section ref={resultsRef} className={`spending-results ${styles.results}`} aria-labelledby="spending-results-title">
        <h2 className="spending-results__title" id="spending-results-title" aria-live="polite">{loadState === 'loading' ? 'Cargando resultados…' : loadState === 'error' ? 'Resultados no disponibles' : `${result.count.toLocaleString('es-ES')} ${result.count === 1 ? 'resultado' : 'resultados'} · ${money(total)} sin impuestos`}</h2>
        {loadState === 'ready' && result.undated_count > 0 ? <p className="spending-results__undated">Incluye {result.undated_count.toLocaleString('es-ES')} resultados con fecha dudosa. Sus importes forman parte del total; no se les asigna una fecha inventada.</p> : null}
        <p className="spending-results__unit">Suma de resultados de adjudicación del histórico filtrado. Un expediente puede contener varios resultados o lotes.</p>
        {loadState === 'ready' && result.count === 0 ? <p className={`spending-results__empty ${styles.empty}`}>No hay resultados disponibles para esos filtros. Nuestra cobertura de las fuentes es incompleta.</p> : null}
        <ol className={`spending-results__list ${styles.list}`}>
          {visible.map((row) => <li className={`spending-result ${styles.card}`} key={row.award_key}>
            <article className="spending-result__article">
              <p className="spending-result__date">{row.decision_date ?? `Fecha dudosa · original: ${row.decision_date_source}`} · expediente {row.contract_id}{row.lot_id ? ` · lote ${row.lot_id}` : ' · lote no publicado'}</p>
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
          <button className="spending-results__previous" disabled={loadState !== 'ready' || currentPage === 0} onClick={() => animate(() => { setLoadState('loading'); setPage(currentPage - 1); })}>Anterior</button>
          <span className="spending-results__page">Página {currentPage + 1} de {lastPage + 1}</span>
          <button className="spending-results__next" disabled={loadState !== 'ready' || result.next_cursor === null} onClick={() => animate(() => { setLoadState('loading'); setCursors((prior) => [...prior.slice(0, currentPage + 1), result.next_cursor]); setPage(currentPage + 1); })}>Siguiente</button>
        </nav>
      </section>
      <footer className={`spending-method ${styles.method}`}>
        <h2 className="spending-method__title">Qué puedes comprobar y qué falta</h2>
        <p className="spending-method__scope">Todas las adjudicaciones elegibles del histórico disponible, usando la última versión no ambigua dentro del corpus congelado. Incluye {audit.capture_entries.toLocaleString('es-ES')} capturas XML verificadas. No prueba pagos, ejecución, irregularidades ni cobertura completa de la contratación pública.</p>
        <p className="spending-method__date-corrections">{audit.date_corrections} fechas corregidas; {audit.unresolved_dates} fechas dudosas conservadas sin asignarles un año. El calendario y el CSV usan las fechas corregidas cuando hay una regla de corrección; el CSV conserva también la fecha original. El paquete fuente y los XML conservan los datos recibidos.</p>
        <p className="spending-method__dates">El manifest original etiqueta 31/03/2025; sus filas contienen capturas de 31/03/2025 y 30/06/2025. Estos resultados incluyen adjudicaciones y formalizaciones, contadas una sola vez por resultado elegible. Ninguna de esas fechas convierte el corte en datos actuales.</p>
        <p className="spending-method__review">Revisión comunitaria pendiente: 0 personas externas han validado este recorrido; 0 reproducciones externas registradas.</p>
        <p className="spending-method__credit">Fuente: Plataforma de Contratación del Sector Público. Captura y transformación: Vota Con La Chola. Las variantes tipográficas convergen para filtrar y sumar; cada fila conserva el nombre literal de la fuente.</p>
        <div className={`spending-method__links ${styles.actions}`}><a className="spending-method__audit" href={`${base}audit.json`}>Selección y exclusiones</a><a className="spending-method__hashes" href={`${base}manifest.json`}>Hashes de todos los archivos</a><a className="spending-method__rights" href="https://github.com/gsusI/vota-con-la-chola/blob/main/docs/legal/data-rights.md">Derechos de reutilización</a></div>
        <p className="spending-method__checksum">SHA-256 del ZIP: <code className={`spending-method__hash ${styles.hash}`}>{release.archive_sha256}</code></p>
      </footer>
    </main>
  );
}
