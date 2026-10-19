import Figure from "../components/Figure";
import HousingChart from "./HousingChart";
import HousingTable from "./HousingTable";
import { Explain } from "./explain";
import { Bars, C, NAMES, PEER_LEGEND, PeerPanels, at, joinEs, num, pct, thousands } from "./common";

const EU_PEERS = ["EU27_2020", "DE", "FR", "IT", "PT"];
const last = (rows) => rows[rows.length - 1];

export function SalePricesFigure({ sale, bases, source }) {
  const series = [
    { id: "ipv", label: "Precio de compraventa, ajustado por calidad (INE, IPV)", shortLabel: "Compraventa INE", color: C.aqua, emphasis: true, points: sale.ipv_idx },
    { id: "tx", label: "Valor medio escriturado ante notario (Ministerio de Vivienda)", shortLabel: "Escrituras", color: C.orange, points: sale.transactions_idx },
    { id: "appraisal", label: "Valor tasado por m² (Ministerio de Vivienda)", shortLabel: "Tasación", color: C.blue, points: sale.appraisal_idx },
  ];
  const lastYear = Math.min(...series.map((s) => last(s.points).year));
  const up = (s) => at(s.points, lastYear) - 100;
  const ipvMin = sale.ipv_idx.reduce((a, b) => (b.value < a.value ? b : a));
  return (
    <Figure
      id="compraventa"
      title={`El precio de compraventa ha subido un ${num(bases.sale_price_change_pct["2019"], 0)} % desde 2019 y un ${num(bases.sale_price_change_pct["2007"], 0)} % desde el máximo de 2007; la tasación, un ${num(bases.appraisal_change_pct["2019"], 0)} % y un ${num(bases.appraisal_change_pct["2007"], 0)} %: la tasación se queda corta`}
      dek={`Tres medidas del precio de la vivienda, en índice 2015 = 100 (2015 es solo la base del índice, no el punto de comparación: arriba se compara con 2007 y 2019; desde el mínimo de 2013 el precio de compraventa ha subido un ${num(bases.sale_price_change_pct["2013"], 0)} %). El índice del INE compara viviendas parecidas a partir de las escrituras (descuenta que se vendan pisos más grandes o mejor situados); el valor medio escriturado es la media simple de lo que se paga; la tasación es lo que estima el tasador para el banco. Con precios de compraventa, un piso de 90 m² costaría ${num(last(sale.years_ipv_chained).value)} años de salario en ${last(sale.years_ipv_chained).year}, no los ${num(at(sale.years_ipv_chained, 2015))} de 2015.`}
      legend={series}
      sources={[
        source("ine_tempus", "INE, Índice de Precios de Vivienda (IPV)", "https://www.ine.es/jaxiT3/Tabla.htm?t=80271"),
        source("mivau_boletin", "Ministerio de Vivienda, valor de las transacciones y valor tasado", "https://apps.fomento.gob.es/BoletinOnline2/?nivel=2&orden=34000000"),
      ]}
      notes={[
        `El IPV empieza en 2007 y su mínimo fue ${num(ipvMin.value, 0)} en ${ipvMin.year}. Los «años de salario con precio de compraventa» encadenan el IPV al valor tasado de 2015 (la única forma de pasar un índice a euros); es una estimación, no un dato publicado.`,
      ]}
      table={
        <HousingTable
          series={[
            ...series.map((s) => ({ ...s, unit: "index" })),
            { id: "eur", label: "Valor medio escriturado (€)", points: sale.transactions_eur, unit: "eur" },
            { id: "years", label: "Años de salario con precio de compraventa", points: sale.years_ipv_chained, unit: "years" },
          ]}
        />
      }
    >
      <HousingChart series={series} unit="index" digits={0} xMin={2004} xMax={lastYear} ariaLabel="Precio de compraventa frente a valor de tasación, índice 2015 = 100" />
      <Explain
        shows="Cuánto ha cambiado el precio de la vivienda desde 2015 según tres fuentes oficiales distintas."
        read={`Todas valen 100 en 2015. Si una línea está en ${num(at(sale.ipv_idx, lastYear), 0)}, el precio es un ${num(up(series[0]), 0)} % mayor que en 2015. Cuanto más se separan, más difieren las fuentes: desde 2018 la compraventa sube más deprisa que la tasación.`}
        notSay="No da el precio de un piso concreto ni el de cada ciudad, y los índices no son comparables en nivel entre sí: solo en evolución."
      />
    </Figure>
  );
}

export function RegionalPriceFigure({ regions, homeM2, capacity, source }) {
  const netYear = capacity.years_net_median_sale_price.at(-1).year;
  const netNational = capacity.years_net_median_sale_price.at(-1).value;
  const grossNational = capacity.years_gross_avg.find((p) => p.year === netYear)?.value;
  const rows = regions.rows.filter((row) => row.years_salary?.[regions.to] != null).sort((a, b) => b.years_salary[regions.to] - a.years_salary[regions.to]);
  const top = rows[0];
  const bottom = last(rows);
  const max = Math.max(...rows.flatMap((row) => Object.values(row.years_salary)));
  const rise = (base) => [...rows].filter((row) => row.years_salary[base] != null).sort((a, b) => (b.years_salary[regions.to] - b.years_salary[base]) - (a.years_salary[regions.to] - a.years_salary[base]))[0];
  const biggestRise = rise(2015);
  const biggest2008 = rise(2008);
  const above2008 = rows.filter((row) => row.years_salary[2008] != null && row.years_salary[regions.to] > row.years_salary[2008]);
  return (
    <Figure
      id="regiones-precio"
      title={`Un piso de ${homeM2} m² cuesta ${num(top.years_salary[regions.to])} años de salario bruto medio en ${top.name} y ${num(bottom.years_salary[regions.to])} en ${bottom.name}`}
      dek={`Años de salario bruto medio de cada comunidad para pagar un piso de ${homeM2} m² al valor tasado medio de esa comunidad, ${regions.to}. Es la medida bruta, la única con salario por comunidad para todos los años; con el sueldo neto mediano y el precio de compraventa, como en la cifra principal de la página, todas las barras serían bastante más largas (en España, ${num(netNational)} años frente a ${num(grossNational)} en ${netYear}). Frente a 2008, al final de la burbuja, ${above2008.length ? `solo ${above2008.map((row) => row.name).join(" y ")} ${above2008.length > 1 ? "están" : "está"} más cara${above2008.length > 1 ? "s" : ""} hoy` : "todas están hoy más baratas"} (lo que más ha subido respecto a 2008 es ${biggest2008.name}: ${num(biggest2008.years_salary[2008])} → ${num(biggest2008.years_salary[regions.to])}); frente a 2015, el año más barato, sube en casi todas, sobre todo en ${biggestRise.name} (${num(biggestRise.years_salary[2015])} → ${num(biggestRise.years_salary[regions.to])}).`}
      legend={[
        { id: "last", label: String(regions.to), color: C.blue },
        { id: "2015", label: "2015", color: C.peer },
      ]}
      legendKind="bar"
      sources={[
        source("mivau_boletin", "Ministerio de Vivienda, valor tasado por comunidad", "https://apps.fomento.gob.es/BoletinOnline2/?nivel=2&orden=35000000"),
        source("ine_tempus", "INE, ETCL por comunidad (tabla 6061)", "https://www.ine.es/jaxiT3/Tabla.htm?t=6061"),
      ]}
      notes={["Ceuta y Melilla no tienen salario en la ETCL. Valor tasado (no precio de compraventa) y media de toda la comunidad: la capital y la costa suelen estar por encima."]}
      table={
        <details className="vizTable">
          <summary>Ver los datos en tabla</summary>
          <div className="vizTable__scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">Comunidad</th>
                  <th scope="col">2008</th>
                  <th scope="col">2015</th>
                  <th scope="col">{regions.to}</th>
                  <th scope="col">€/m² {regions.to}</th>
                  <th scope="col">Salario anual {regions.to}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.code}>
                    <td>{row.name}</td>
                    <td>{row.years_salary[2008] != null ? num(row.years_salary[2008]) : "—"}</td>
                    <td>{num(row.years_salary[2015])}</td>
                    <td>{num(row.years_salary[regions.to])}</td>
                    <td>{thousands(row.price_m2)} €</td>
                    <td>{thousands(row.wage)} €</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      }
    >
      <Bars
        rows={rows.flatMap((row) => [
          { id: `${row.code}-last`, label: row.name, value: row.years_salary[regions.to], color: C.blue, text: `${num(row.years_salary[regions.to])} años` },
          { id: `${row.code}-2015`, label: "", value: row.years_salary[2015], color: C.peer, text: `${num(row.years_salary[2015])} en 2015` },
        ])}
        max={max}
        label="Años de salario por comunidad"
      />
      <Explain
        shows="La misma medida que el primer gráfico, pero con el precio y el salario de cada comunidad."
        read="Barra azul: hoy. Barra gris: 2015, el año más barato de la serie nacional. Una barra azul mucho más larga que la gris indica que el precio ha subido más que los salarios de esa comunidad."
        notSay="No distingue municipios: dentro de una comunidad conviven ciudades caras y pueblos baratos. Tampoco recoge el alquiler."
      />
    </Figure>
  );
}

export function RentFigure({ rents, source }) {
  const series = [
    { id: "ipva", label: "Alquiler declarado a Hacienda (INE, IPVA)", shortLabel: "Alquiler (IPVA)", color: C.orange, emphasis: true, points: rents.ipva_idx },
    { id: "wage", label: "Salario bruto medio (INE, ETCL)", shortLabel: "Salario", color: C.blue, points: rents.wage_idx },
    { id: "cpi", label: "Precios de consumo (IPCA)", shortLabel: "Precios", color: C.ref, points: rents.cpi_idx },
    { id: "appraisal", label: "Valor tasado de la vivienda", shortLabel: "Vivienda (tasación)", color: C.aqua, points: rents.appraisal_idx },
  ];
  const y = last(rents.ipva_idx).year;
  const chg = (rows) => at(rows, y) - 100;
  const since = (rows, base) => (at(rows, y) / at(rows, base) - 1) * 100;
  return (
    <Figure
      id="alquiler"
      title={`Los alquileres declarados a Hacienda subieron un ${num(since(rents.ipva_idx, 2011), 0)} % de 2011 a ${y} y un ${num(since(rents.ipva_idx, 2019), 0)} % desde 2019, como los precios (${num(since(rents.cpi_idx, 2011), 0)} % y ${num(since(rents.cpi_idx, 2019), 0)} %) y los salarios (${num(since(rents.wage_idx, 2011), 0)} % y ${num(since(rents.wage_idx, 2019), 0)} %)`}
      dek={`Índice 2015 = 100. El IPVA del INE mide la renta de todos los contratos de alquiler declarados en el IRPF, también los firmados hace años, que solo se actualizan con el IPC o lo pactado. Por eso sube despacio: el encarecimiento que sufre quien busca piso hoy está en los contratos nuevos, que esta serie diluye.`}
      legend={series}
      sources={[
        source("ine_tempus", "INE, Índice de Precios de Vivienda en Alquiler", "https://www.ine.es/jaxiT3/Tabla.htm?t=59056"),
        source("eurostat_sdmx", "Eurostat, IPCA (prc_hicp_aind)", "https://ec.europa.eu/eurostat/databrowser/view/prc_hicp_aind/default/table"),
        source("ine_tempus", "INE, ETCL"),
      ]}
      notes={[
        `El IPVA se publica con dos años de retraso (último dato: ${y}) y no cubre País Vasco ni Navarra (tienen su propia Hacienda). El Sistema Estatal de Referencia de Precios del Alquiler del Ministerio usa la misma fuente fiscal; no hay una serie oficial larga del precio de los contratos nuevos.`,
      ]}
      table={<HousingTable series={series.map((s) => ({ ...s, unit: "index" }))} />}
    >
      <HousingChart series={series} unit="index" digits={0} xMin={rents.ipva_idx[0].year} xMax={last(rents.cpi_idx).year} ariaLabel="Alquiler frente a salarios, precios y vivienda en propiedad" />
      <Explain
        shows="Cómo han evolucionado desde 2015 el alquiler medio de todos los contratos, el salario, los precios de consumo y el valor de la vivienda en propiedad."
        read="Todas las líneas valen 100 en 2015. Si el alquiler va por debajo del salario, pagarlo cuesta una parte menor del sueldo medio; si va por encima, mayor."
        notSay="No dice cuánto cuesta alquilar hoy un piso nuevo, que es lo que más ha subido según los portales inmobiliarios (que no son fuente oficial). Tampoco el esfuerzo de cada hogar."
      />
    </Figure>
  );
}

export function RentPeersFigure({ rents, source }) {
  const data = rents.hicp_rent_real;
  const es = last(data.ES);
  const max = Math.max(...Object.values(data).flatMap((rows) => rows.map((p) => p.value)));
  return (
    <Figure
      id="alquiler-pares"
      title={`Descontada la inflación, el alquiler de la cesta del IPCA en España está en ${num(es.value, 0)} (2015 = 100); en la UE, en ${num(last(data.EU27_2020).value, 0)}`}
      dek="Alquiler efectivo de la vivienda en el índice armonizado de precios de consumo, dividido por el índice general: si baja, el alquiler sube menos que el resto de precios. Todos los países miden igual (contratos vigentes), así que sí permite comparar."
      legend={PEER_LEGEND}
      sources={[source("eurostat_sdmx", "Eurostat, IPCA: CP041 alquileres efectivos y CP00 general", "https://ec.europa.eu/eurostat/databrowser/view/prc_hicp_aind/default/table")]}
      notes={["El IPCA de alquileres de España es conocido por subir poco: pesa mucho el parque de contratos antiguos y renovados. Sirve para comparar con otros países que miden igual, no para medir lo que paga un nuevo inquilino."]}
      table={<HousingTable series={["ES", ...EU_PEERS].map((geo) => ({ id: geo, label: NAMES[geo], points: data[geo] || [], unit: "index" }))} />}
    >
      <PeerPanels data={data} spain="ES" peers={EU_PEERS} unit="index" digits={0} xMin={1996} xMax={es.year} yMax={max} panelNote={(rows) => `${num(last(rows).value, 0)} en ${last(rows).year}`} />
      <Explain
        shows="La evolución del alquiler, descontada la inflación, en España y en países comparables desde 1996."
        read="100 es el nivel de 2015. Una línea que baja significa que el alquiler medio de los contratos vigentes sube menos que los demás precios."
        notSay="No compara niveles (cuántos euros cuesta alquilar en cada país) ni el alquiler de los contratos nuevos."
      />
    </Figure>
  );
}

export function RegionalGapFigure({ regions, source }) {
  const rows = regions.rows.filter((row) => row.gap_per_1000 != null && !["ES63", "ES64"].includes(row.code)).sort((a, b) => b.gap_per_1000 - a.gap_per_1000);
  const max = Math.max(...rows.map((row) => row.gap_per_1000));
  const worst = rows.filter((row) => row.ratio != null && row.ratio < 0.5);
  return (
    <Figure
      id="brecha-regional"
      title={`El déficit no es uniforme: en ${joinEs(worst.map((row) => row.name))} se terminó menos de media vivienda por cada hogar nuevo entre ${regions.from + 1} y ${regions.to}`}
      dek={`Hogares nuevos menos viviendas terminadas en cada comunidad, por cada 1.000 hogares que había en ${regions.from}. Cuanto más larga la barra, más hogares se han formado sin una vivienda nueva que los acompañe. Entre paréntesis, viviendas terminadas por cada hogar nuevo. Las comunidades con barra cero o negativa construyeron tanto o más de lo que crecieron sus hogares.`}
      legendKind="bar"
      sources={[
        source("mivau_boletin", "Ministerio de Vivienda, viviendas terminadas por comunidad"),
        source("eurostat_sdmx", "Eurostat, hogares por región (EPA)", "https://ec.europa.eu/eurostat/databrowser/view/lfst_r_lfsd2hh/default/table"),
      ]}
      notes={[
        `Viviendas terminadas = libres + protegidas, sumadas de ${regions.from + 1} a ${regions.to}; hogares nuevos = hogares de la EPA en ${regions.to} menos en ${regions.from}. Las cifras regionales de la EPA tienen error de muestreo, sobre todo en comunidades pequeñas; Ceuta y Melilla se omiten por eso.`,
      ]}
      table={
        <details className="vizTable">
          <summary>Ver los datos en tabla</summary>
          <div className="vizTable__scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">Comunidad</th>
                  <th scope="col">Viviendas terminadas</th>
                  <th scope="col">Hogares nuevos</th>
                  <th scope="col">Viviendas por hogar nuevo</th>
                  <th scope="col">Déficit (hogares sin vivienda nueva)</th>
                  <th scope="col">Por 1.000 hogares</th>
                </tr>
              </thead>
              <tbody>
                {regions.rows.map((row) => (
                  <tr key={row.code}>
                    <td>{row.name}</td>
                    <td>{thousands(row.completed)}</td>
                    <td>{row.net_households != null ? thousands(row.net_households) : "—"}</td>
                    <td>{row.ratio != null ? num(row.ratio, 2) : "—"}</td>
                    <td>{row.gap != null ? thousands(row.gap) : "—"}</td>
                    <td>{row.gap_per_1000 != null ? num(row.gap_per_1000) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      }
    >
      <Bars
        rows={rows.map((row) => ({
          id: row.code,
          label: row.name,
          value: row.gap_per_1000,
          color: row.gap_per_1000 > 0 ? C.orange : C.aqua,
          text: `${num(row.gap_per_1000)}${row.ratio != null ? ` (${num(row.ratio, 2)} viv./hogar)` : ""}`,
        }))}
        max={max}
        label="Déficit de viviendas por comunidad"
      />
      <Explain
        shows="Dónde se han formado más hogares de los que se han construido viviendas en los últimos doce años."
        read="Una barra de 30 significa que por cada 1.000 hogares de 2013 se formaron 30 hogares más que viviendas se terminaron. «0,40 viviendas por hogar nuevo» quiere decir que se terminaron 4 viviendas por cada 10 hogares nuevos."
        notSay="No cuenta el parque vacío que podría cubrir ese déficit ni dónde dentro de cada comunidad se forman los hogares. Una comunidad sin déficit puede tener ciudades con escasez."
      />
    </Figure>
  );
}

export function PopulationFigure({ drivers, source }) {
  const mig = drivers.net_migration_per_1000;
  const pop = drivers.population_es;
  const max = Math.max(...Object.values(mig).flatMap((rows) => rows.filter((p) => p.year >= 1990).map((p) => p.value)));
  const lastEs = last(mig.ES);
  const natural = drivers.natural_growth_per_1000_es;
  const firstNegative = natural.find((p) => p.value < 0 && natural.filter((q) => q.year > p.year).every((q) => q.value < 0));
  return (
    <Figure
      id="poblacion"
      title={`España recibe ${num(lastEs.value, 1)} inmigrantes netos por 1.000 habitantes al año (${lastEs.year}), ${num(lastEs.value / last(mig.EU27_2020).value, 1)} veces la media de la UE: es la fuente del aumento de población que alimenta la demanda de vivienda`}
      dek={`La población residente pasó de ${num(at(pop, 2000) / 1e6, 1)} millones en 2000 a ${num(at(pop, 2008) / 1e6, 1)} en 2008, ${num(at(pop, 2019) / 1e6, 1)} en 2019 y ${num(last(pop).value / 1e6, 1)} en ${last(pop).year}. Desde ${firstNegative ? firstNegative.year : "2015"} mueren más personas de las que nacen, así que todo el crecimiento viene de la migración. Cuántos hogares nuevos se deben a más población y cuántos a hogares más pequeños, por tramos, en el gráfico siguiente.`}
      legend={PEER_LEGEND}
      sources={[
        source("eurostat_sdmx", "Eurostat, demo_gind (migración neta y población)", "https://ec.europa.eu/eurostat/databrowser/view/demo_gind/default/table"),
        source("bde_indicadores_vivienda", "INE, hogares de la EPA (vía Banco de España)"),
      ]}
      notes={[
        "Migración neta de Eurostat incluye un ajuste estadístico entre censos y padrón.",
      ]}
      table={
        <HousingTable
          series={[
            ...["ES", ...EU_PEERS].map((geo) => ({ id: `m-${geo}`, label: `Migración neta ${NAMES[geo]} (‰)`, points: mig[geo] || [], unit: "index" })),
            { id: "nat", label: "Crecimiento natural España (‰)", points: natural, unit: "index" },
          ]}
        />
      }
    >
      <PeerPanels data={mig} spain="ES" peers={EU_PEERS} unit="index" xMin={1990} xMax={lastEs.year} yMax={max} panelNote={(rows) => `${num(last(rows).value)} por 1.000 en ${last(rows).year}`} />
      <Explain
        shows="Cuánta gente llega a cada país por migración, en ‰ de la población, desde 1990."
        read="Una línea por encima de cero significa que llega más gente de la que se va. España tuvo dos olas, en los años 2000 y desde mediados de los 2010, separadas por años de salida neta durante la crisis."
        notSay="No dice si la inmigración «causa» la subida de precios: también aporta trabajadores a la construcción y renta. Solo dice cuántos hogares nuevos hay que alojar."
      />
    </Figure>
  );
}

export function HouseholdSizeFigure({ drivers, source }) {
  const size = drivers.household_size;
  const es = size.ES;
  const max = Math.max(...Object.values(size).flatMap((rows) => rows.map((p) => p.value)));
  return (
    <Figure
      id="tamano-hogar"
      title={`Los hogares españoles se achican, de ${num(es[0].value, 1)} personas en ${es[0].year} a ${num(last(es).value, 1)} en ${last(es).year}, pero siguen siendo más grandes que la media de la UE (${num(last(size.EU27_2020).value, 1)})`}
      dek="Número medio de personas por hogar. Con la misma población, hogares más pequeños necesitan más viviendas: es la segunda fuente de demanda junto a la inmigración."
      legend={PEER_LEGEND}
      sources={[source("eurostat_sdmx", "Eurostat, ilc_lvph01", "https://ec.europa.eu/eurostat/databrowser/view/ilc_lvph01/default/table")]}
      notes={["Encuesta EU-SILC; el tamaño medio cae por el envejecimiento (más personas mayores solas), menos hijos y más rupturas, pero también sube cuando los jóvenes no pueden emanciparse."]}
      table={<HousingTable series={["ES", ...EU_PEERS].map((geo) => ({ id: geo, label: NAMES[geo], points: size[geo] || [], unit: "index", digits: 2 }))} />}
    >
      <PeerPanels data={size} spain="ES" peers={EU_PEERS} unit="index" digits={2} xMin={2005} xMax={last(es).year} yMax={max} panelNote={(rows) => `${num(last(rows).value, 2)} en ${last(rows).year}`} />
      <Explain
        shows="Cuántas personas viven, de media, en cada hogar en España y en países comparables."
        read="Cuanto más baja la línea, más hogares (y viviendas) hacen falta para la misma población."
        notSay="No separa si los hogares son más pequeños por elección o por falta de vivienda: los jóvenes que siguen con sus padres hacen los hogares más grandes."
      />
    </Figure>
  );
}

export function TouristFigure({ drivers, regions, source }) {
  const nights = drivers.platform_nights_per_capita;
  const year = Math.min(...["ES", "EU27_2020"].map((geo) => last(nights[geo]).year));
  const order = ["ES", ...EU_PEERS].filter((geo) => at(nights[geo], year) != null).sort((a, b) => at(nights[b], year) - at(nights[a], year));
  const maxN = Math.max(...order.map((geo) => at(nights[geo], year)));
  const reg = regions.rows.filter((row) => row.tourist_pct != null).sort((a, b) => b.tourist_pct - a.tourist_pct);
  const top = reg[0];
  const MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
  const period = `${MONTHS[Number(regions.tourist_period.slice(5, 7)) - 1]} de ${regions.tourist_period.slice(0, 4)}`;
  return (
    <Figure
      id="turisticos"
      title={`En España se pasan ${num(at(nights.ES, year), 1)} noches por habitante y año en alojamientos reservados por plataformas, ${num(at(nights.ES, year) / at(nights.EU27_2020, year), 1)} veces la media de la UE; las viviendas turísticas son el ${num(regions.tourist_es, 2)} % del parque (${num(top.tourist_pct, 1)} % en ${top.name})`}
      dek={`Arriba, pernoctaciones de corta estancia reservadas en Airbnb, Booking, Expedia y Tripadvisor, divididas por la población (${year}). Abajo, viviendas anunciadas como turísticas sobre el total de viviendas de cada comunidad (INE, ${period}).`}
      legendKind="bar"
      sources={[
        source("eurostat_sdmx", "Eurostat, tour_ce_omn12 (estadística experimental)", "https://ec.europa.eu/eurostat/databrowser/view/tour_ce_omn12/default/table"),
        source("ine_tempus", "INE, viviendas turísticas (estadística experimental)", "https://www.ine.es/jaxiT3/Tabla.htm?t=39365"),
      ]}
      notes={["Ambas son estadísticas experimentales basadas en anuncios y reservas en plataformas: no distinguen viviendas enteras de habitaciones en la de Eurostat, y la del INE cuenta viviendas anunciadas, no alquiladas. El efecto sobre los precios se concentra en barrios y municipios concretos que una media autonómica diluye."]}
      table={
        <HousingTable
          series={[
            ...["ES", ...EU_PEERS].map((geo) => ({ id: geo, label: `Noches por habitante ${NAMES[geo]}`, points: nights[geo] || [], unit: "index", digits: 2 })),
          ]}
        />
      }
    >
      <div className="vizStack">
        <div>
          <h3>Noches en alojamientos de plataforma por habitante, {year}</h3>
          <Bars
            rows={order.map((geo) => ({ id: geo, label: NAMES[geo], value: at(nights[geo], year), color: geo === "ES" ? C.blue : geo === "EU27_2020" ? C.ref : C.peer, text: num(at(nights[geo], year), 2) }))}
            max={maxN}
            label="Noches por habitante"
          />
        </div>
        <div>
          <h3>Viviendas turísticas sobre el total de viviendas, por comunidad ({period})</h3>
          <Bars
            rows={reg.map((row) => ({ id: row.code, label: row.name, value: row.tourist_pct, color: C.orange, text: pct(row.tourist_pct, 2) }))}
            max={top.tourist_pct}
            label="Viviendas turísticas por comunidad"
          />
        </div>
      </div>
      <Explain
        shows="Cuánto pesa el alojamiento turístico de plataforma en España frente a otros países y en cada comunidad."
        read="Arriba, más noches por habitante es más presión turística sobre las viviendas. Abajo, un 4 % quiere decir que 4 de cada 100 viviendas de la comunidad se anuncian como turísticas."
        notSay="No mide cuántas de esas viviendas se habrían alquilado a residentes ni su efecto en el precio; para eso harían falta datos por barrio."
      />
    </Figure>
  );
}

export function NormsFigure({ norms, source }) {
  if (!norms?.total?.length) return null;
  const total = norms.total;
  const peak = total.reduce((a, b) => (b.value > a.value ? b : a));
  const series = [
    { id: "total", label: "Total", color: C.ref, points: total },
    { id: "estatal", label: "Estatales", shortLabel: "Estatales", color: C.blue, emphasis: true, points: norms.estatal || [] },
    { id: "autonomica", label: "Autonómicas publicadas en el BOE", shortLabel: "Autonómicas", color: C.orange, points: norms.autonomica || [] },
  ];
  const firstYear = total[0].year;
  const laws = norms.state_laws || [];
  return (
    <Figure
      id="normas"
      title={`El BOE publicó ${thousands(total.reduce((a, b) => a + b.value, 0))} disposiciones generales sobre vivienda entre ${firstYear} y ${last(total).year}; el máximo fue ${peak.year}, con ${thousands(peak.value)}`}
      dek="Disposiciones generales (sección I del BOE) cuyo título trata de vivienda, alquiler, arrendamientos urbanos o rehabilitación, por año. Incluye las leyes autonómicas, que también se publican en el BOE, pero no los decretos y órdenes autonómicos, que solo salen en los boletines de cada comunidad."
      legend={series}
      sources={[source("vclc_housing_curated", "BOE, sumarios diarios (API de datos abiertos), contados con scripts/boe_housing_norms.py", "https://www.boe.es/datosabiertos/api/api.php")]}
      notes={["Contar normas mide actividad legislativa, no calidad ni efecto: una ley de vivienda pesa más que diez órdenes de ayudas. La selección se hace por el título; la lista completa con cada identificador del BOE está en el JSON."]}
      table={
        <>
          <HousingTable series={series.map((s) => ({ ...s, unit: "count" }))} unit="count" />
          {laws.length ? (
            <details className="vizTable">
              <summary>Ver las leyes y reales decretos-leyes estatales ({laws.length})</summary>
              <div className="vizTable__scroll">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Fecha</th>
                      <th scope="col">Norma</th>
                    </tr>
                  </thead>
                  <tbody>
                    {laws.map((law) => (
                      <tr key={law.boe_id}>
                        <td>{law.date}</td>
                        <td>
                          <a href={law.url} rel="noopener noreferrer" target="_blank">
                            {law.title}
                          </a>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          ) : null}
        </>
      }
    >
      <HousingChart series={series} unit="count" xMin={firstYear} xMax={last(total).year} ariaLabel="Normas sobre vivienda publicadas en el BOE por año" />
      <Explain
        shows="Cuántas normas generales sobre vivienda aparecen cada año en el BOE, separando las del Estado de las leyes autonómicas."
        read="Cada punto es el número de disposiciones de ese año. Los picos suelen coincidir con planes estatales de vivienda, crisis (2008–2013) o reformas del alquiler."
        notSay="No dice si las normas funcionan ni cuánto cambian: no mide su contenido. Tampoco cuenta la normativa urbanística municipal, que decide cuánto suelo se puede construir."
      />
    </Figure>
  );
}
