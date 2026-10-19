import { readPublicJson } from "../../static-snapshot.mjs";
import { StaticRouteHero } from "../../static-route-components";
import ChapterParo from "./ch1_paro";
import ChapterCiclo from "./ch2_ciclo";
import ChapterCausas from "./ch3_causas";
import ChapterCalidad, { IntermittencyFigure } from "./ch4_calidad";
import ChapterProductividad from "./ch5_productividad";
import ChapterCapacidad from "./capacidad";
import ChapterComposicion from "./composicion";
import { LimitsCard, MethodCard } from "./sections";
import { Conclusion, Glossary, Summary } from "./summary";
import DatoMataRelato from "./relato";
import { num } from "./format.mjs";

export const metadata = {
  title: "El paro en España: ¿estructural o cíclico? | Vota Con La Chola",
  description:
    "Paro desde 1960 frente a Europa, ciclo y dualidad de contratos, causas de la brecha, fijos discontinuos, regiones, productividad y salarios, con fuentes oficiales, rupturas de serie y datos descargables.",
};

const pct = (value, digits = 1) => `${num(value, digits)} %`;

export default function EmpleoPage() {
  const data = readPublicJson("visualizaciones/data/empleo.json", null);
  if (!data) throw new Error("Missing visualizaciones/data/empleo.json");
  const h = data.headline;
  const g = h.productivity_growth_pct;
  const downloads = "/visualizaciones/data/empleo.csv";
  const events = data.events || [];
  const evYear = (id) => events.find((e) => e.id === id)?.year;
  const epaBreaks = events.filter((e) => e.kind === "series_break").map((e) => ({ year: e.year, label: `EPA ${e.year}`, row: 1 }));
  const reform = (id, label, row = 0) => (evYear(id) ? [{ year: evYear(id), label, row }] : []);

  return (
    <main className="shell vizArticle">
      <StaticRouteHero
        eyebrow="Visualizaciones · datos públicos"
        title="El paro en España: ¿estructural o cíclico?"
        summary="Ponemos a prueba una hipótesis: que el paro español es estructural, casi el doble del europeo en cada ciclo desde 1980, y que la productividad por hora apenas ha crecido desde 1995. Medimos también las causas que se suelen señalar y publicamos lo que contradice la hipótesis."
        actions={[
          { href: "#resumen", label: "Resumen en seis datos" },
          { href: downloads, label: "Descargar datos (CSV)" },
          { href: "/visualizaciones/data/empleo.json", label: "JSON con procedencia" },
          { href: "#metodo", label: "Método y fuentes" },
        ]}
      />

      <section className="vizStats" aria-label="Cifras clave">
        <div className="card vizStat">
          <span className="vizStat__label">Paro en {h.last_year}</span>
          <span className="vizStat__value">{pct(h.es_last)}</span>
          <span className="vizStat__note">
            frente al {pct(h.eu27_last)} de la UE-27: {num(h.ratio_eu27_last, 2)} veces
          </span>
        </div>
        <div className="card vizStat">
          <span className="vizStat__label">Paro de España sobre el europeo desde {h.hypothesis_from}</span>
          <span className="vizStat__value">×{num(h.ratio_mean_since, 2)}</span>
          <span className="vizStat__note">
            de media; por encima de 1,5 veces en {h.years_ratio_ge_1_5} de {h.years_since} años (UE-15)
          </span>
        </div>
        <div className="card vizStat">
          <span className="vizStat__label">
            Productividad por hora, {h.productivity_base}–{h.productivity_last}
          </span>
          <span className="vizStat__value">+{num(g.ESP)} %</span>
          <span className="vizStat__note">
            frente a +{num(g.EU27)} % en la UE-27; desde 2008, +{num(data.composition?.base_year.productivity.rows.find((r) => r.base === 2008)?.ESP)} % frente a +
            {num(data.composition?.base_year.productivity.rows.find((r) => r.base === 2008)?.EU27)} %
          </span>
        </div>
        <div className="card vizStat">
          <span className="vizStat__label">Asalariados temporales</span>
          <span className="vizStat__value">{pct(h.temp_es_last)}</span>
          <span className="vizStat__note">
            {pct(h.temp_es_2021)} en 2021; fijos discontinuos (EPA): {num(h.discont_k_2021, 0)} mil → {num(h.discont_k_last, 0)} mil
          </span>
        </div>
      </section>

      <DatoMataRelato data={data} />
      <Summary data={data} />
      <ChapterParo data={data} epaBreaks={epaBreaks} reform={reform} />
      <ChapterCiclo data={data} events={events} />
      <ChapterCausas data={data} events={events} />
      <ChapterCalidad data={data} epaBreaks={epaBreaks} reform={reform}>
        <IntermittencyFigure data={data} reform={reform} />
      </ChapterCalidad>
      <ChapterProductividad data={data} />
      <ChapterCapacidad data={data} />
      <ChapterComposicion data={data} />
      <Conclusion data={data} />
      <Glossary />
      <LimitsCard />
      <MethodCard data={data} downloads={downloads} events={events} />
    </main>
  );
}
