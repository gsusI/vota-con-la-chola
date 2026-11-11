"use client";

// Causal relations of slice 3 (employment, immigration) and the capacity part of slice 4 (healthcare). Same conventions
// as CausalMap.js and HousingMap.js: each link with an `edge` opens its card; values are the deviation in the year.
export const LABOUR_NODES = [
  { id: "smi", label: "Salario mínimo", kind: "lever" },
  { id: "hours", label: "Jornada máxima", kind: "lever" },
  { id: "quota", label: "Cuota de autónomos", kind: "lever" },
  { id: "migration", label: "Inmigración neta", kind: "context" },
  { id: "mir", label: "Plazas MIR", kind: "lever" },
  { id: "hspend", label: "Gasto sanitario extra", kind: "lever" },
  { id: "low_wages", label: "Masa salarial", kind: "var" },
  { id: "hour_cost", label: "Coste por hora de quien trabaja 40 h", kind: "var" },
  { id: "jobs", label: "Empleo de los afectados", kind: "var" },
  { id: "self", label: "Autónomos", kind: "var" },
  { id: "residents", label: "Residentes", kind: "var" },
  { id: "workers", label: "Ocupados nuevos", kind: "var" },
  { id: "revenue", label: "Impuestos y cotizaciones que pagan", kind: "var" },
  { id: "services", label: "Gasto en servicios y pensiones", kind: "var" },
  { id: "demand", label: "Demanda sanitaria", kind: "var" },
  { id: "doctors", label: "Médicos especialistas", kind: "var" },
  { id: "capacity", label: "Capacidad de operar y atender", kind: "var" },
  { id: "list", label: "Lista de espera quirúrgica", kind: "var" },
  { id: "budget", label: "Cuentas públicas", kind: "var" },
];

export const LABOUR_LINKS = [
  { from: "smi", to: "low_wages", edge: "L01_smi_affected", sign: "+" },
  { from: "smi", to: "jobs", edge: "L02_smi_employment", sign: "−" },
  { from: "low_wages", to: "budget", edge: "L01_smi_affected", sign: "+" },
  { from: "hours", to: "hour_cost", edge: "L04_hours_affected", sign: "+" },
  { from: "hour_cost", to: "jobs", edge: "L05_hours_employment", sign: "−" },
  { from: "quota", to: "self", edge: "L08_self_employed_elasticity", sign: "−" },
  { from: "quota", to: "budget", edge: "L07_self_employed_base", sign: "+" },
  { from: "jobs", to: "budget", edge: "E11_revenue_per_job", sign: "+" },
  { from: "migration", to: "residents", edge: "M01_migration_variants", sign: "+" },
  { from: "residents", to: "workers", edge: "M02_migrant_employment", sign: "+" },
  { from: "workers", to: "revenue", edge: "M03_migrant_wage", sign: "+" },
  { from: "residents", to: "services", edge: "M05_congestible_spending", sign: "+" },
  { from: "residents", to: "demand", edge: "M04_migrant_health_use", sign: "+" },
  { from: "mir", to: "doctors", edge: "S01_training_lag", sign: "+" },
  { from: "doctors", to: "capacity", edge: "S08_doctors_stock", sign: "+" },
  { from: "hspend", to: "capacity", edge: "S04_capacity_money", sign: "+" },
  { from: "demand", to: "list", edge: "S07_waiting_list_flow", sign: "+" },
  { from: "capacity", to: "list", edge: "S07_waiting_list_flow", sign: "−" },
  { from: "revenue", to: "budget", sign: "+" },
  { from: "services", to: "budget", sign: "−" },
];

const lt = (v) => Number(v).toLocaleString("es-ES");

/** Deviation shown in each node at year index t: [value, unit, digits, suffix, text]. */
export function labourValues(run, t, levers) {
  const s = levers.migScale || (levers.migration === "low" ? -1 : levers.migration === "high" ? 1 : 0);
  const at = (key) => run[key]?.[t] ?? 0;
  return {
    smi: [levers.smi, "pct", 1, "real"],
    hours: [levers.hours ? -levers.hours : 0, "", 1, "", levers.hours ? `${lt(40 - levers.hours)} h a la semana` : null],
    quota: [levers.selfQuota, "eur", 0, "al mes"],
    migration: [s, "", 1, "", s ? `${s > 0 ? "+" : "−"}${lt(Math.abs(s))} × variante oficial` : null],
    mir: [levers.mir, "", 0, "", levers.mir ? `+${lt(levers.mir)} al año` : null],
    hspend: [levers.healthSpend, "pct", 0],
    low_wages: [at("lb_wage_bill_pct"), "pct", 2],
    hour_cost: [at("lb_hour_cost_pct"), "pct", 1],
    jobs: [at("lb_smi_k") + at("lb_hours_k"), "k", 0],
    self: [at("lb_self_k"), "k", 0],
    residents: [at("mig_pop_k"), "k", 0],
    workers: [at("mig_emp_k"), "k", 0],
    revenue: [at("mig_revenue_pp"), "pp", 2, "del PIB"],
    services: [at("mig_spend_pp"), "pp", 2, "del PIB"],
    demand: [at("hl_demand_pct"), "pct", 1],
    doctors: [at("hl_doctors_k"), "k", 1],
    capacity: [at("hl_capacity_pct"), "pct", 1],
    list: [at("hl_list_k"), "k", 0, "pacientes"],
    budget: [-(at("lb_revenue_pp") - at("mig_net_pp") - at("hl_cost_pp")), "pp", 2, "de coste neto"],
  };
}
