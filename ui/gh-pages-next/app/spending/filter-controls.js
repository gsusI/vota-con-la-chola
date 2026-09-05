'use client';

import { useRef, useState } from 'react';
import Select from 'react-select';
import { DayPicker, getDefaultClassNames } from 'react-day-picker';
import { es } from 'react-day-picker/locale';
import 'react-day-picker/style.css';
import styles from './launch.module.css';

const calendarClasses = Object.fromEntries(Object.entries(getDefaultClassNames())
  .map(([key, value]) => [key, /_(enter|exit)$/.test(key) ? value : `${value} spending-calendar__${key.replaceAll('_', '-')}`]));
const parseDate = (value) => new Date(`${value}T12:00:00`);
const isoDate = (date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
const formatDate = (value) => parseDate(value).toLocaleDateString('es-ES');

export function SearchSelect({ id, label, placeholder, values, value, onChange }) {
  const options = values.map((name) => ({ value: name, label: name }));
  return <div className={`spending-filter spending-filter--${id} ${styles.searchField}`}>
    <label className="spending-filter__label" htmlFor={`spending-${id}`}>{label}</label>
    <Select inputId={`spending-${id}`} instanceId={`spending-${id}`} className="spending-search"
      classNamePrefix="spending-search" options={options} value={options.find((option) => option.value === value) || null}
      onChange={(option) => onChange(option?.value || '')} isClearable isSearchable placeholder={placeholder}
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

export function DateRangeField({ start, end, onChange }) {
  const dialogRef = useRef(null);
  const triggerRef = useRef(null);
  const [draft, setDraft] = useState(null);
  const [month, setMonth] = useState(parseDate(start));
  const [session, setSession] = useState(0);
  const selected = draft ? { from: draft } : { from: parseDate(start), to: parseDate(end) };

  function close() {
    dialogRef.current.close();
    triggerRef.current.focus();
  }
  function open() {
    setDraft(null);
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

  return <div className={`spending-date-range ${styles.dateField}`}>
    <span className="spending-date-range__label" id="spending-date-label">Fecha de adjudicación · desde — hasta</span>
    <button className="spending-date-range__trigger" ref={triggerRef} type="button" onClick={open}
      aria-haspopup="dialog" aria-labelledby="spending-date-label spending-date-value">
      <span className="spending-date-range__value" id="spending-date-value">{formatDate(start)} — {formatDate(end)}</span>
      <span className="spending-date-range__icon" aria-hidden="true"> ▾</span>
    </button>
    <dialog className={`spending-date-range__dialog ${styles.calendarDialog}`} ref={dialogRef}
      aria-labelledby="spending-calendar-title" aria-describedby="spending-calendar-help"
      onCancel={(event) => { event.preventDefault(); close(); }}
      onClick={(event) => { if (event.target === event.currentTarget) {
        const box = event.currentTarget.getBoundingClientRect();
        if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) close();
      } }}>
      <h3 className="spending-calendar__title" id="spending-calendar-title">Elige el rango de fechas</h3>
      <p className={`spending-calendar__help ${styles.calendarHelp}`} id="spending-calendar-help" aria-live="polite">
        {draft ? `Desde ${formatDate(isoDate(draft))}. Ahora elige hasta qué día.` : 'Primer clic: desde. Segundo clic: hasta.'}
      </p>
      <DayPicker key={session} mode="range" selected={selected} onDayClick={selectDay}
        month={month} onMonthChange={setMonth} locale={es} autoFocus animate fixedWeeks
        classNames={calendarClasses} captionLayout="dropdown" startMonth={new Date(2000, 0)} endMonth={new Date(2100, 11)} />
      <button className="spending-calendar__cancel" type="button" onClick={close}>Cancelar</button>
    </dialog>
  </div>;
}
