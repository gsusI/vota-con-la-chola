# Codebook Tier 1 (España)

Version: `v1`

Objetivo: definir ejes **operacionales** por dominio (Tier 1) para codificar eventos en un vector “lo que hicieron” con:
- **dirección** (signo),
- **intensidad** (magnitud),
- **confianza** (incertidumbre),
y trazabilidad a evidencia primaria.

Regla: este codebook **no** define “bien/mal”. Solo define **qué dimensión se movió** y en qué sentido. Cualquier ranking o escalar es un “modo” aparte con pesos explícitos.

## Escalas (KISS)

- `direction`: `-1 | 0 | +1`
  - `+1` = “más de X” o “movimiento hacia el polo A del eje” (definido abajo).
  - `-1` = “menos de X” o “movimiento hacia el polo B del eje”.
  - `0` = neutral/no mueve el eje.
- `intensity`: `0.0 .. 1.0`
  - 0.2 pequeño, 0.5 medio, 0.8 grande (guía).
- `confidence`: `0.0 .. 1.0`
  - 0.2 baja (texto ambiguo / implementación incierta).
  - 0.5 media (efecto plausible pero con huecos).
  - 0.8 alta (cambio explícito + evidencia clara).

Regla anti-sesgo: si no es observable con suficiente claridad, **no se imputa**. Se deja sin score (o `confidence` baja con nota explícita).

## Dominios y ejes (Tier 1)

Formato: cada eje define qué significa `+1` y `-1`. No es una recomendación.

### 1) `economia_empleo`

1. `fiscal_stance`
  - `+1`: política fiscal más expansiva (más gasto neto / más déficit aceptado)
  - `-1`: política fiscal más contractiva (recorte neto / más consolidación)
2. `tax_burden_level`
  - `+1`: sube presión fiscal agregada (o amplía base recaudatoria neta)
  - `-1`: baja presión fiscal agregada (o reduce base neta)
3. `tax_progressivity`
  - `+1`: estructura más progresiva (más carga relativa en rentas/beneficios altos)
  - `-1`: estructura menos progresiva / más plana
4. `labor_market_regulation`
  - `+1`: más regulación/protección laboral (costes/despido, rigidez, convenios)
  - `-1`: más flexibilidad/liberalización
5. `business_regulation`
  - `+1`: más carga regulatoria/administrativa para empresas
  - `-1`: simplificación/desregulación
6. `state_intervention_economy`
  - `+1`: más intervención directa (subsidios dirigidos, control, rescates, planificación)
  - `-1`: menos intervención directa / más neutralidad

### 2) `coste_vida`

1. `direct_household_relief`
  - `+1`: más transferencias/bonos/ayudas directas a hogares
  - `-1`: menos transferencias/ayudas directas
2. `indirect_tax_prices`
  - `+1`: subidas netas de impuestos que afectan precios (IVA, especiales)
  - `-1`: bajadas netas (reducciones temporales, exenciones)
3. `price_intervention`
  - `+1`: más intervención en precios (topes, controles, tarifas reguladas)
  - `-1`: menos intervención (más precio de mercado)
4. `energy_price_policy`
  - `+1`: más intervención/subsidio orientado a precio final de energía
  - `-1`: menos intervención/subsidio
5. `competition_supply_measures`
  - `+1`: medidas pro-oferta/competencia (desbloqueos, reducción de cuellos, liberalización)
  - `-1`: medidas que restringen oferta/competencia (o la encarecen) sin compensación
6. `wage_indexation_support`
  - `+1`: más soporte explícito a indexación/subidas salariales/SMI (como política de precios)
  - `-1`: menos soporte / más contención

### 3) `sanidad_salud_publica`

1. `resources_capacity`
  - `+1`: más recursos/capacidad (plantillas, camas, presupuesto, equipamiento)
  - `-1`: menos recursos/capacidad
2. `access_waiting_times`
  - `+1`: medidas explícitas para reducir listas/tiempos de espera (o ampliar acceso)
  - `-1`: medidas que reducen acceso o degradan capacidad de atención
3. `public_health_prevention`
  - `+1`: más prevención/salud pública (vigilancia, vacunación, salud ambiental)
  - `-1`: menos prevención/salud pública
4. `governance_accountability`
  - `+1`: más rendición de cuentas/medición/transparencia clínica-operativa
  - `-1`: menos rendición de cuentas/transparencia
5. `public_private_mix`
  - `+1`: más peso de provisión privada/conciertos/outsourcing
  - `-1`: más provisión pública directa / reversión de outsourcing
6. `centralization_coordination`
  - `+1`: más coordinación/centralización estatal (estándares, compras, mando)
  - `-1`: más autonomía descentralizada (CCAA/centros)

### 4) `educacion_capital_humano`

1. `resources_inputs`
  - `+1`: más recursos/inputs (ratios, becas, infra, formación)
  - `-1`: menos recursos/inputs
2. `evaluation_accountability`
  - `+1`: más evaluación/estándares y accountability (pruebas, métricas, consecuencias)
  - `-1`: menos evaluación/estandarización
3. `school_autonomy_choice`
  - `+1`: más autonomía de centro/elección (modelos, gestión, admisión)
  - `-1`: menos autonomía/elección (más asignación/centralización)
4. `equity_compensation`
  - `+1`: más compensación/soporte a alumnado vulnerable (refuerzo, orientación, inclusión)
  - `-1`: menos compensación/soporte
5. `teacher_professionalization`
  - `+1`: más carrera profesional, incentivos, formación y selección exigente
  - `-1`: menos profesionalización/incentivos
6. `curriculum_centralization`
  - `+1`: currículo más centralizado/mandatado (contenidos, horas, estándares)
  - `-1`: currículo más flexible/local (centros/territorio)

### 5) `vivienda_urbanismo`

1. `supply_expansion`
  - `+1`: medidas que aumentan oferta (suelo, licencias, incentivos a construcción)
  - `-1`: medidas que restringen oferta (o la encarecen) sin compensación
2. `rent_regulation`
  - `+1`: más regulación de alquiler (topes, indexación, límites a subidas)
  - `-1`: menos regulación (más libertad de precio/contrato)
3. `tenant_protection`
  - `+1`: más protección del inquilino (desahucios, prórrogas, garantías)
  - `-1`: menos protección / más capacidad de ejecución del propietario
4. `public_housing_investment`
  - `+1`: más vivienda pública/social (inversión, parque, adquisición)
  - `-1`: menos inversión/parque público
5. `land_use_density`
  - `+1`: más densificación/edificabilidad permitida (o simplificación de planeamiento)
  - `-1`: menos densidad/edificabilidad (o más restricciones urbanísticas)
6. `housing_tax_incentives`
  - `+1`: más incentivos fiscales/subsidios a vivienda (compra/alquiler)
  - `-1`: menos incentivos fiscales/subsidios

### 6) `impuestos_gasto_fiscalidad`

1. `revenue_policy`
  - `+1`: subidas netas de ingresos (impuestos, bases, lucha fraude con efecto recaudatorio)
  - `-1`: bajadas netas de ingresos
2. `spending_policy`
  - `+1`: subidas netas de gasto comprometido
  - `-1`: bajadas netas de gasto comprometido
3. `deficit_debt_tolerance`
  - `+1`: más tolerancia a déficit/deuda (relaja objetivos/reglas)
  - `-1`: más consolidación/estrictez fiscal (refuerza reglas/objetivos)
4. `budget_transparency`
  - `+1`: más transparencia presupuestaria/ejecución/publicación de microdatos
  - `-1`: menos transparencia
5. `spending_evaluation_audits`
  - `+1`: más evaluación/auditoría de gasto (spending reviews, métricas)
  - `-1`: menos evaluación/auditoría
6. `tax_base_structure`
  - `+1`: ampliación de bases (menos exenciones) o cambios estructurales que estabilizan ingresos
  - `-1`: más exenciones/erosión de bases o volatilidad estructural

### 7) `justicia_seguridad`

1. `police_security_resources`
  - `+1`: más recursos operativos (policía, medios, coordinación)
  - `-1`: menos recursos operativos
2. `penal_policy_severity`
  - `+1`: endurecimiento penal/administrativo (penas, tipificación, sanción)
  - `-1`: ablandamiento/despenalización (o reducción de penas)
3. `due_process_safeguards`
  - `+1`: refuerzo de garantías/procesos (defensa, control judicial, límites)
  - `-1`: reducción de garantías / ampliación discrecional de poderes
4. `justice_system_capacity`
  - `+1`: más capacidad/eficiencia judicial (plazas, digitalización, procedimientos)
  - `-1`: menos capacidad/eficiencia
5. `anti_corruption_integrity`
  - `+1`: más controles/anticorrupción (auditorías, incompatibilidades, transparencia)
  - `-1`: menos controles/anticorrupción
6. `surveillance_powers`
  - `+1`: ampliación de capacidades de vigilancia/interceptación/retención de datos
  - `-1`: restricción de esas capacidades

### 8) `energia_medio_ambiente`

1. `decarbonization_speed`
  - `+1`: transición más rápida (objetivos más estrictos, calendario acelerado)
  - `-1`: transición más lenta (objetivos más laxos, retrasos)
2. `renewables_support`
  - `+1`: más incentivos/apoyo a renovables (subastas, permisos, red)
  - `-1`: menos apoyo/obstáculos
3. `fossil_dependency`
  - `+1`: más dependencia/soporte a fósiles (subsidios, expansión, permisos)
  - `-1`: menos dependencia/retirada de soporte
4. `energy_price_intervention`
  - `+1`: más intervención en precio final (topes, tarifas, compensaciones)
  - `-1`: menos intervención (más precio de mercado)
5. `emissions_pollution_regulation`
  - `+1`: regulación ambiental más estricta (emisiones, calidad aire/agua, sanción)
  - `-1`: regulación más laxa
6. `grid_resilience_investment`
  - `+1`: más inversión en red/almacenamiento/resiliencia y seguridad de suministro
  - `-1`: menos inversión

### 9) `infraestructura_transporte`

1. `infrastructure_investment`
  - `+1`: más inversión en infraestructura (capex)
  - `-1`: menos inversión
2. `maintenance_safety`
  - `+1`: más mantenimiento/seguridad (carreteras, rail, inspección, siniestralidad)
  - `-1`: menos mantenimiento/seguridad
3. `public_transport_support`
  - `+1`: más soporte a transporte público (subsidios, ampliación, prioridad)
  - `-1`: menos soporte
4. `user_fees_pricing`
  - `+1`: más tarificación al usuario (peajes, tasas, pricing dinámico)
  - `-1`: menos tarificación (o gratuidad/subsidio mayor)
5. `modal_shift_policy`
  - `+1`: políticas que favorecen modos no coche (PT/bici/peatón) frente a coche
  - `-1`: políticas que favorecen coche/viario frente a PT/activos
6. `planning_centralization`
  - `+1`: más centralización/estandarización de planificación y ejecución
  - `-1`: más descentralización/autonomía territorial

### 10) `proteccion_social_pensiones`

1. `benefit_generosity`
  - `+1`: mayor generosidad/importe/cobertura de prestaciones
  - `-1`: menor generosidad/cobertura
2. `eligibility_strictness`
  - `+1`: criterios de acceso más estrictos/condicionales
  - `-1`: criterios más inclusivos
3. `means_testing`
  - `+1`: más focalización por renta/patrimonio (means-tested)
  - `-1`: más universalidad (menos means-test)
4. `pension_sustainability_reforms`
  - `+1`: reformas pro-sostenibilidad (edad efectiva, factor, contribuciones)
  - `-1`: reversión/relajación de reformas de sostenibilidad
5. `activation_services`
  - `+1`: más políticas activas (formación, intermediación, condicionalidad activa)
  - `-1`: menos políticas activas
6. `family_child_support`
  - `+1`: más apoyo explícito a familias/infancia (transferencias, permisos, servicios)
  - `-1`: menos apoyo

## Mapeo al esquema SQLite (cuando se implemente)

- `docs/domain_taxonomy_es.md` -> `domains`
- este codebook -> `policy_axes`
- scores por evento -> `policy_event_axis_scores(method=human:v1|rule:v1|model:v1, notes=...)`

