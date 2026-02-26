function normalizeFilterValue(value) {
  if (Array.isArray(value)) {
    return value.join(" ");
  }
  if (value === null || value === undefined) {
    return "";
  }
  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }
  return String(value);
}

function isEmptyValue(value) {
  return normalizeFilterValue(value).trim() === "";
}

function toNumber(value) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  const parsed = Number(String(value ?? "").trim());
  return Number.isFinite(parsed) ? parsed : null;
}

function isRegexExpression(expression) {
  return /^\/.*\/[a-z]*$/i.test(expression);
}

function parseRegexExpression(expression) {
  const lastSlash = expression.lastIndexOf("/");
  if (lastSlash <= 0) {
    return null;
  }
  const pattern = expression.slice(1, lastSlash);
  const flags = expression.slice(lastSlash + 1);
  try {
    return new RegExp(pattern, flags);
  } catch {
    return null;
  }
}

function matchNumericExpression(rawExpression, rawValue) {
  const expression = rawExpression.trim();
  const valueNum = toNumber(rawValue);
  if (valueNum === null) {
    return false;
  }

  const rangeMatch = expression.match(/^(-?\d+(?:\.\d+)?)\s*\.\.\s*(-?\d+(?:\.\d+)?)$/);
  if (rangeMatch) {
    const left = Number(rangeMatch[1]);
    const right = Number(rangeMatch[2]);
    const min = Math.min(left, right);
    const max = Math.max(left, right);
    return valueNum >= min && valueNum <= max;
  }

  const opMatch = expression.match(/^(<=|>=|!=|=|<|>)\s*(-?\d+(?:\.\d+)?)$/);
  if (!opMatch) {
    return false;
  }

  const op = opMatch[1];
  const target = Number(opMatch[2]);
  if (op === "<") return valueNum < target;
  if (op === ">") return valueNum > target;
  if (op === "<=") return valueNum <= target;
  if (op === ">=") return valueNum >= target;
  if (op === "=") return valueNum === target;
  return valueNum !== target;
}

function matchStringExpression(rawExpression, rawValue) {
  const expression = rawExpression.trim();
  const value = normalizeFilterValue(rawValue);
  const valueLower = value.toLowerCase();

  if (!expression) {
    return true;
  }

  if (isRegexExpression(expression)) {
    const regex = parseRegexExpression(expression);
    if (!regex) {
      return false;
    }
    return regex.test(value);
  }

  const exactMatch = expression.match(/^(?:=|==)\s*(.+)$/);
  if (exactMatch) {
    return valueLower === exactMatch[1].trim().toLowerCase();
  }

  const notExactMatch = expression.match(/^!=\s*(.+)$/);
  if (notExactMatch) {
    return valueLower !== notExactMatch[1].trim().toLowerCase();
  }

  const startsWithMatch = expression.match(/^\^\s*(.+)$/);
  if (startsWithMatch) {
    return valueLower.startsWith(startsWithMatch[1].trim().toLowerCase());
  }

  const endsWithMatch = expression.match(/^(.+)\$$/);
  if (endsWithMatch) {
    return valueLower.endsWith(endsWithMatch[1].trim().toLowerCase());
  }

  const notContainsMatch = expression.match(/^!\s*(.+)$/);
  if (notContainsMatch) {
    return !valueLower.includes(notContainsMatch[1].trim().toLowerCase());
  }

  return valueLower.includes(expression.toLowerCase());
}

function matchAtomicExpression(rawExpression, rawValue) {
  const expression = rawExpression.trim();
  if (!expression) {
    return true;
  }

  if (matchNumericExpression(expression, rawValue)) {
    return true;
  }

  return matchStringExpression(expression, rawValue);
}

function matchesFilterExpression(rawExpression, rawValue) {
  const expression = String(rawExpression || "").trim();
  if (!expression) {
    return true;
  }

  const andTerms = expression.split("&&").map((term) => term.trim()).filter(Boolean);
  if (!andTerms.length) {
    return true;
  }

  return andTerms.every((andTerm) => {
    const orTerms = andTerm.split("||").map((term) => term.trim()).filter(Boolean);
    if (!orTerms.length) {
      return true;
    }
    return orTerms.some((orTerm) => matchAtomicExpression(orTerm, rawValue));
  });
}

const TEXT_OPERATORS = [
  { value: "contains", label: "contiene" },
  { value: "not_contains", label: "no contiene" },
  { value: "equals", label: "igual" },
  { value: "not_equals", label: "distinto" },
  { value: "starts_with", label: "empieza por" },
  { value: "ends_with", label: "termina en" },
  { value: "regex", label: "regex" },
  { value: "empty", label: "vacío" },
  { value: "not_empty", label: "no vacío" },
];

const NUMBER_OPERATORS = [
  { value: "eq", label: "=" },
  { value: "ne", label: "!=" },
  { value: "gt", label: ">" },
  { value: "gte", label: ">=" },
  { value: "lt", label: "<" },
  { value: "lte", label: "<=" },
  { value: "empty", label: "vacío" },
  { value: "not_empty", label: "no vacío" },
];

function defaultOperatorForType(filterType) {
  return filterType === "number" ? "eq" : "contains";
}

function normalizeFilterSpec(rawSpec, filterType) {
  if (rawSpec && typeof rawSpec === "object" && !Array.isArray(rawSpec)) {
    return {
      op: String(rawSpec.op || defaultOperatorForType(filterType)),
      value: String(rawSpec.value || ""),
      valueTo: String(rawSpec.valueTo || ""),
    };
  }
  if (typeof rawSpec === "string") {
    return {
      op: defaultOperatorForType(filterType),
      value: rawSpec,
      valueTo: "",
    };
  }
  return {
    op: defaultOperatorForType(filterType),
    value: "",
    valueTo: "",
  };
}

function normalizeFilterSpecs(rawSpec, filterType) {
  if (Array.isArray(rawSpec)) {
    const specs = rawSpec
      .map((item) => normalizeFilterSpec(item, filterType))
      .filter((item) => item && typeof item === "object");
    return specs.length ? specs : [normalizeFilterSpec(null, filterType)];
  }
  return [normalizeFilterSpec(rawSpec, filterType)];
}

function isFilterSpecEmpty(spec) {
  const op = String(spec?.op || "");
  if (op === "empty" || op === "not_empty") {
    return false;
  }
  return String(spec?.value || "").trim() === "";
}

function matchesStructuredFilter(spec, rawValue, filterType) {
  const op = String(spec?.op || defaultOperatorForType(filterType));
  const value = String(spec?.value || "").trim();
  const valueTo = String(spec?.valueTo || "").trim();

  if (op === "empty") {
    return isEmptyValue(rawValue);
  }
  if (op === "not_empty") {
    return !isEmptyValue(rawValue);
  }

  if (filterType === "number") {
    const left = toNumber(rawValue);
    if (left === null) {
      return false;
    }
    const right = toNumber(value);
    if (right === null) {
      return true;
    }
    if (op === "eq") return left === right;
    if (op === "ne") return left !== right;
    if (op === "gt") return left > right;
    if (op === "gte") return left >= right;
    if (op === "lt") return left < right;
    if (op === "lte") return left <= right;
    return true;
  }

  const text = normalizeFilterValue(rawValue);
  const textLower = text.toLowerCase();
  const needle = value.toLowerCase();

  if (!needle && op !== "regex") {
    return true;
  }

  if (op === "contains") return textLower.includes(needle);
  if (op === "not_contains") return !textLower.includes(needle);
  if (op === "equals") return textLower === needle;
  if (op === "not_equals") return textLower !== needle;
  if (op === "starts_with") return textLower.startsWith(needle);
  if (op === "ends_with") return textLower.endsWith(needle);
  if (op === "regex") {
    if (!value) return true;
    let maybeRegex = null;
    if (isRegexExpression(value)) {
      maybeRegex = parseRegexExpression(value);
    } else {
      try {
        maybeRegex = new RegExp(value, "i");
      } catch {
        maybeRegex = null;
      }
    }
    if (!maybeRegex) return false;
    return maybeRegex.test(text);
  }
  return true;
}

export function applyColumnFilters(rows, filters, valueGetter) {
  if (!Array.isArray(rows) || !rows.length) {
    return rows || [];
  }
  const entries = Object.entries(filters || {}).filter(([, raw]) => {
    if (Array.isArray(raw)) {
      return raw.some((item) => !isFilterSpecEmpty(item));
    }
    if (raw && typeof raw === "object" && !Array.isArray(raw)) {
      return !isFilterSpecEmpty(raw);
    }
    return String(raw || "").trim() !== "";
  });
  if (!entries.length) {
    return rows;
  }
  return rows.filter((row) => {
    for (const [columnKey, rawFilter] of entries) {
      const firstItem = Array.isArray(rawFilter) ? rawFilter[0] : rawFilter;
      const filterType = firstItem && typeof firstItem === "object" ? String(firstItem.type || "text") : "text";
      const value = valueGetter(columnKey, row);
      if (Array.isArray(rawFilter)) {
        const activeClauses = rawFilter.filter((item) => !isFilterSpecEmpty(item));
        if (activeClauses.some((item) => !matchesStructuredFilter(item, value, filterType))) {
          return false;
        }
      } else if (rawFilter && typeof rawFilter === "object" && !Array.isArray(rawFilter)) {
        if (!matchesStructuredFilter(rawFilter, value, filterType)) {
          return false;
        }
      } else if (!matchesFilterExpression(rawFilter, value)) {
        return false;
      }
    }
    return true;
  });
}

export function ColumnFiltersRow({ tableId, columns, filtersByTable, onFilterChange }) {
  const tableFilters = filtersByTable[tableId] || {};
  return (
    <tr className="tableFilterRow">
      {columns.map((column) => (
        <th key={`${tableId}:${column.key}`}>
          {(() => {
            const filterType = column.type === "number" ? "number" : "text";
            const specs = normalizeFilterSpecs(tableFilters[column.key], filterType);
            const operators = filterType === "number" ? NUMBER_OPERATORS : TEXT_OPERATORS;
            const help =
              filterType === "number"
                ? "Filtro numerico guiado. Puedes agregar multiples filtros por columna (AND)."
                : "Filtro de texto guiado (contiene, igual, empieza, termina, regex)";

            const emitSpecs = (nextSpecs) =>
              onFilterChange(
                tableId,
                column.key,
                nextSpecs.map((item) => ({ ...item, type: filterType })),
              );

            const updateSpec = (index, nextSpec) => {
              const next = specs.map((item, idx) => (idx === index ? nextSpec : item));
              emitSpecs(next);
            };

            const addSpec = () => {
              emitSpecs([...specs, normalizeFilterSpec(null, filterType)]);
            };

            const removeSpec = (index) => {
              if (specs.length <= 1) {
                emitSpecs([normalizeFilterSpec(null, filterType)]);
                return;
              }
              emitSpecs(specs.filter((_, idx) => idx !== index));
            };

            return (
              <div className="tableFilterControl">
                {specs.map((spec, idx) => {
                  const showMainValue = spec.op !== "empty" && spec.op !== "not_empty";
                  return (
                    <div className="tableFilterClauseRow" key={`${column.key}:${idx}`}>
                      <select
                        className="tableFilterSelect"
                        value={spec.op}
                        onChange={(event) => updateSpec(idx, { ...spec, op: event.target.value })}
                        aria-label={`Operador de ${column.label}`}
                        title={help}
                      >
                        {operators.map((operator) => (
                          <option key={operator.value} value={operator.value}>
                            {operator.label}
                          </option>
                        ))}
                      </select>
                      {showMainValue ? (
                        <input
                          className="tableFilterInput"
                          type={filterType === "number" ? "number" : "text"}
                          value={spec.value}
                          onChange={(event) => updateSpec(idx, { ...spec, value: event.target.value })}
                          placeholder={column.placeholder || "valor"}
                          title={help}
                          aria-label={`Valor de ${column.label}`}
                        />
                      ) : null}
                      <button
                        type="button"
                        className="tableFilterMiniButton"
                        onClick={() => removeSpec(idx)}
                        aria-label={`Quitar filtro de ${column.label}`}
                        title="Quitar filtro"
                      >
                        -
                      </button>
                    </div>
                  );
                })}
                <button
                  type="button"
                  className="tableFilterMiniButton"
                  onClick={addSpec}
                  aria-label={`Agregar filtro en ${column.label}`}
                  title="Agregar otro filtro (AND)"
                >
                  + filtro
                </button>
              </div>
            );
          })()}
        </th>
      ))}
    </tr>
  );
}
