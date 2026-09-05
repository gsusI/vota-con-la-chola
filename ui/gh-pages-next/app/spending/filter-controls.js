'use client';

import { useEffect, useRef, useState } from 'react';
import Select from 'react-select';
import { DayPicker, getDefaultClassNames } from 'react-day-picker';
import { es } from 'react-day-picker/locale';
import 'react-day-picker/style.css';
import styles from './launch.module.css';

const calendarClasses = Object.fromEntries(Object.entries(getDefaultClassNames())
  .map(([key, value]) => [key, /_(enter|exit)$/.test(key) ? value : `${value} spending-calendar__${key.replaceAll('_', '-')}`]));
const parseDate = (value) => new Date(`${value}T12:00:00`);
const isoDate = (date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
const formatDate = (value) => {
  const date = parseDate(value);
  return `${String(date.getDate()).padStart(2, '0')}/${String(date.getMonth() + 1).padStart(2, '0')}/${date.getFullYear()}`;
};
const parseTextDate = (value) => {
  const text = value.trim();
  const isoMatch = /^(\d{4})-(\d{2})-(\d{2})$/.exec(text);
  const localMatch = /^(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})$/.exec(text);
  const parts = isoMatch ? [isoMatch[1], isoMatch[2], isoMatch[3]]
    : localMatch ? [localMatch[3], localMatch[2], localMatch[1]] : null;
  if (!parts) return null;
  const normalized = `${parts[0]}-${parts[1].padStart(2, '0')}-${parts[2].padStart(2, '0')}`;
  const date = parseDate(normalized);
  return Number.isNaN(date.getTime()) || isoDate(date) !== normalized ? null : normalized;
};

export function SearchSelect({ id, label, placeholder, values, value, onChange, disabled = false }) {
  const options = values.map((name) => ({ value: name, label: name }));
  return <div className={`spending-filter spending-filter--${id} ${styles.searchField}`}>
    <label className="spending-filter__label" htmlFor={`spending-${id}`}>{label}</label>
    <Select inputId={`spending-${id}`} instanceId={`spending-${id}`} className="spending-search"
      classNamePrefix="spending-search" options={options} value={options.find((option) => option.value === value) || null}
      onChange={(option) => onChange(option?.value || '')} isClearable isSearchable placeholder={placeholder}
      isDisabled={disabled}
      noOptionsMessage={() => 'Sin coincidencias'} loadingMessage={() => 'Buscando…'}
      screenReaderStatus={({ count }) => `${count} opciones disponibles.`}
      ariaLiveMessages={{
        guidance: () => 'Escribe para buscar. Usa las flechas y Enter para seleccionar; Escape para cerrar.',
        onFilter: ({ resultsMessage }) => resultsMessage,
        onFocus: ({ focused }) => focused ? focused.label : '',
        onChange: ({ label: selectedLabel }) => selectedLabel ? `Seleccionado: ${selectedLabel}` : 'Filtro eliminado',
      }}
      styles={{
        control: (base) => ({ ...base, minHeight: 48, borderColor: '#718b7e', borderRadius: 8 }),
        input: (base) => ({ ...base, margin: 0, padding: 0 }),
        menu: (base) => ({ ...base, zIndex: 5 }),
        option: (base, state) => ({ ...base, color: state.isSelected ? '#fff' : '#192923', backgroundColor: state.isSelected ? '#195f45' : state.isFocused ? '#e6f0e8' : '#fff' }),
      }}
    />
  </div>;
}

export function DateRangeField({ start, end, resetToken, onChange, disabled = false }) {
  const dialogRef = useRef(null);
  const triggerRef = useRef(null);
  const [draft, setDraft] = useState(null);
  const [month, setMonth] = useState(parseDate(start));
  const [session, setSession] = useState(0);
  const [texts, setTexts] = useState({ start: formatDate(start), end: formatDate(end) });
  const [error, setError] = useState('');
  const [errorKey, setErrorKey] = useState('');
  const selected = draft ? { from: draft } : { from: parseDate(start), to: parseDate(end) };

  useEffect(() => {
    setTexts({ start: formatDate(start), end: formatDate(end) });
    setError('');
    setErrorKey('');
  }, [start, end, resetToken]);

  function close() {
    dialogRef.current.close();
    triggerRef.current.focus();
  }
  function open() {
    setDraft(null);
    setError('');
    setErrorKey('');
    setMonth(parseDate(start));
    setSession((prior) => prior + 1);
    dialogRef.current.showModal();
  }
  function selectDay(day) {
    if (!draft) { setDraft(day); return; }
    const dates = [isoDate(draft), isoDate(day)].sort();
    close();
    onChange({ start: dates[0], end: dates[1] });
  }
  function editDate(key, text) {
    setTexts((prior) => ({ ...prior, [key]: text }));
    setError('');
    setErrorKey('');
  }
  function commitDate(key) {
    const value = parseTextDate(texts[key]);
    if (!value) {
      setError(`${key === 'start' ? 'Desde' : 'Hasta'} debe ser una fecha válida en formato dd/mm/aaaa.`);
      setErrorKey(key);
      return;
    }
    const currentValue = key === 'start' ? start : end;
    if (value === currentValue) {
      setTexts((prior) => ({ ...prior, [key]: formatDate(value) }));
      setError('');
      setErrorKey('');
      return;
    }
    if (key === 'start' && value > end) {
      setError('Desde no puede ser posterior a Hasta.');
      setErrorKey(key);
      return;
    }
    if (key === 'end' && value < start) {
      setError('Hasta no puede ser anterior a Desde.');
      setErrorKey(key);
      return;
    }
    setError('');
    setErrorKey('');
    setTexts((prior) => ({ ...prior, [key]: formatDate(value) }));
    onChange({ start, end, [key]: value });
  }
  function handleDateKeyDown(event, key) {
    if (event.key === 'Enter') {
      event.preventDefault();
      commitDate(key);
    }
    if (event.key === 'Escape') {
      setTexts({ start: formatDate(start), end: formatDate(end) });
      setError('');
      setErrorKey('');
    }
  }

  return <div className={`spending-date-range ${styles.dateField}`}>
    <span className="spending-date-range__label" id="spending-date-label">Fecha de adjudicación</span>
    <div className={`spending-date-range__inputs ${styles.dateInputs}`}>
      <label className="spending-date-range__start-label" htmlFor="spending-date-start">
        Desde
        <input className="spending-date-range__start-input" id="spending-date-start" type="text"
          inputMode="numeric" autoComplete="off" placeholder="dd/mm/aaaa" value={texts.start}
          disabled={disabled}
          aria-invalid={errorKey === 'start'} aria-describedby="spending-date-format spending-date-error"
          onChange={(event) => editDate('start', event.target.value)}
          onBlur={() => commitDate('start')} onKeyDown={(event) => handleDateKeyDown(event, 'start')} />
      </label>
      <label className="spending-date-range__end-label" htmlFor="spending-date-end">
        Hasta
        <input className="spending-date-range__end-input" id="spending-date-end" type="text"
          inputMode="numeric" autoComplete="off" placeholder="dd/mm/aaaa" value={texts.end}
          disabled={disabled}
          aria-invalid={errorKey === 'end'} aria-describedby="spending-date-format spending-date-error"
          onChange={(event) => editDate('end', event.target.value)}
          onBlur={() => commitDate('end')} onKeyDown={(event) => handleDateKeyDown(event, 'end')} />
      </label>
      <button className="spending-date-range__trigger" ref={triggerRef} type="button" onClick={open}
        disabled={disabled}
        aria-haspopup="dialog" aria-labelledby="spending-date-label spending-date-calendar-label">
        <span className="spending-date-range__calendar-icon" aria-hidden="true">▦</span>
        <span className="spending-date-range__calendar-label" id="spending-date-calendar-label">Elegir rango en calendario</span>
      </button>
    </div>
    <p className={`spending-date-range__format ${styles.dateFormat}`} id="spending-date-format">Formato: dd/mm/aaaa. Puedes editar cada fecha por separado.</p>
    <p className={`spending-date-range__error ${styles.dateError}`} id="spending-date-error" role="alert">{error}</p>
    <dialog className={`spending-date-range__dialog ${styles.calendarDialog}`} ref={dialogRef}
      aria-labelledby="spending-calendar-title" aria-describedby="spending-calendar-help"
      onCancel={(event) => { event.preventDefault(); close(); }}
      onClick={(event) => { if (event.target === event.currentTarget) {
        const box = event.currentTarget.getBoundingClientRect();
        if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) close();
      } }}>
      <h3 className="spending-calendar__title" id="spending-calendar-title">Elige el rango de fechas</h3>
      <p className={`spending-calendar__help ${styles.calendarHelp}`} id="spending-calendar-help" aria-live="polite">
        {draft ? `Desde ${formatDate(isoDate(draft))}. Ahora elige hasta qué día.` : 'Primer clic: desde. Segundo clic: hasta. También puedes editar cada campo por separado.'}
      </p>
      <DayPicker key={session} mode="range" selected={selected} onSelect={(_range, day) => selectDay(day)}
        month={month} onMonthChange={setMonth} locale={es} autoFocus animate fixedWeeks
        classNames={calendarClasses} captionLayout="dropdown" startMonth={new Date(2000, 0)} endMonth={new Date(2100, 11)} />
      <button className="spending-calendar__cancel" type="button" onClick={close}>Cancelar</button>
    </dialog>
  </div>;
}
