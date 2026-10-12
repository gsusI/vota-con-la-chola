from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts import voting_aid_motion_texts as mt

REPO = Path(__file__).resolve().parent.parent
SEED = REPO / "etl/data/seeds/voting_aid_motion_texts_v1.json"
HIGHLIGHTS = REPO / "ui/gh-pages-next/public/citizen/data/voting_aid_highlights_v1.json"

INITIATIVE_HTML = """
<h3>Boletines</h3><ul class="boletines">
 <li>
  <div>BOCG. Congreso de los Diputados Núm. D-20 de 06/10/2023 Pág.: 45 <br />Iniciativa</div></td>
  <div><a href="/busqueda-de-publicaciones?...(BOCG-15-D-20.CODI.)">texto íntegro</a> |
   <a href="/public_oficiales/L15/CONG/BOCG/D/BOCG-15-D-20.PDF#page=45" target="_blank" /><i></i> PDF</a></div>
 </li>
 <li>
  <div>BOCG. Congreso de los Diputados Núm. D-59 de 28/12/2023 Pág.: 78 <br />Enmiendas</div></td>
  <div><a href="/public_oficiales/L15/CONG/BOCG/D/BOCG-15-D-59-C1.PDF#page=78" /> PDF</a></div>
 </li>
 <li>
  <div>BOCG. Congreso de los Diputados Núm. D-59 de 28/12/2023 Pág.: 80 <br />Aprobación por el Pleno</div></td>
  <div><a href="/public_oficiales/L15/CONG/BOCG/D/BOCG-15-D-59-C1.PDF#page=80" /> PDF</a></div>
 </li>
</ul>
<h3>Diarios de Sesiones</h3>
<div id="_iniciativas_customHtmlDiarios">DS. Congreso de los Diputados Núm.14 de 19/12/2023 Pág: 56 Pleno
 <a href="/public_oficiales/L15/CONG/DS/PL/DSCD-15-PL-14.PDF#page=56">PDF</a></div>
<div class="votaciones"><a href='https://www.congreso.es/webpublica/opendata/votaciones/Leg15/Sesion013/20231219/Votacion004/VOT_20231219233113.json'>JSON</a></div>
Concluido - (Aprobado con modificaciones) desde 19/12/2023
"""

# pdftotext -layout output: pages separated by form feeds, running headers, an earlier motion's tail.
ORIGINAL_PAGES = (
    "                    BOLETÍN OFICIAL DE LAS CORTES GENERALES\n"
    "                         CONGRESO DE LOS DIPUTADOS\n"
    "Serie D   Núm. 20                     6 de octubre de 2023                    Pág. 45\n"
    "                  7. Punto de otra proposición.»\n"
    "              162/000014\n"
    "              A la Mesa del Congreso de los Diputados\n"
    "                 El Grupo Parlamentario X presenta la siguiente Proposición no de ley sobre la línea\n"
    "              Pau-Canfranc-Zaragoza, para su debate en el Pleno.\n"
    "              Exposición de motivos\n"
    "                   El artículo citado «entre comillas» no es la parte dispositiva.\n"
    "                                                                 cve: BOCG-15-D-20\n"
    "\f"
    "                    BOLETÍN OFICIAL DE LAS CORTES GENERALES\n"
    "Serie D   Núm. 20                     6 de octubre de 2023                    Pág. 46\n"
    "              Proposición no de Ley\n"
    "                    «El Congreso de los Diputados insta al Gobierno a:\n"
    "                  1. Retomar las negociaciones con Francia sobre el trazado Oloron-\n"
    "              Canfranc y su financia-\n"
    "              ción europea.\n"
    "                  2. Convocar la reunión «cuatripartita» con las regiones:\n"
    "                  a) Aragón.\n"
    "                  b) Nueva Aquitania.»\n"
    "                 Palacio del Congreso de los Diputados, 28 de septiembre de 2023.—Portavoz.\n"
    "              162/000015\n"
    "              A la Mesa del Congreso de los Diputados\n"
    "                    «El Congreso de los Diputados insta al Gobierno a otra cosa.»\n"
)

APPROVAL_PAGES = (
    "Serie D   Núm. 59                     28 de diciembre de 2023                 Pág. 78\n"
    "              162/000014\n"
    "                  Se ordena la publicación de las enmiendas formuladas.\n"
    "              Enmienda\n"
    "                   «1. Texto de una enmienda que no se aprobó.»\n"
    "\f"
    "Serie D   Núm. 59                     28 de diciembre de 2023                 Pág. 79\n"
    "                  El Pleno del Congreso de los Diputados, en su sesión del día de hoy, ha acordado\n"
    "              aprobar con modificaciones la Proposición no de Ley sobre la línea, publicada en el\n"
    "              «BOCG. Congreso de los Diputados», serie D, núm. 20, en los siguientes términos:\n"
    "                    «El Congreso de los Diputados acuerda instar al Gobierno a:\n"
    "                   1. Impulsar la modernización de la vía.\n"
    "                   2. Cooperar con Aragón y Francia.»\n"
    "              PREGUNTAS PARA RESPUESTA ORAL\n"
    "              181/000001\n"
)


class TestMatching(unittest.TestCase):
    def test_motion_object_and_terms(self) -> None:
        text = "Proposición no de Ley del Grupo Parlamentario VOX, sobre la ampliación del Puerto.\nSe vota en los términos de la enmienda transaccional presentada por el Grupo Parlamentario Socialista."
        self.assertEqual(mt.motion_object(text), "sobre la ampliación del Puerto.")
        self.assertTrue(mt.voted_terms(text).startswith("Se vota en los términos de la enmienda transaccional"))
        self.assertEqual(mt.motion_object("Moción consecuencia de interpelación urgente del Grupo Parlamentario Popular en el Congreso, sobre vivienda."), "sobre vivienda.")
        self.assertEqual(mt.motion_object("Votación de conjunto de la Proposición de Ley Orgánica de amnistía (corresponde a otra)."), "Orgánica de amnistía.")
        self.assertTrue(all(len(q.split()) <= 4 for q in mt.search_queries("sobre la reapertura de la línea ferroviaria internacional Pau-Canfranc-Zaragoza")))

    def test_text_status(self) -> None:
        self.assertEqual(mt.text_status_for(True, True, "Se vota en los términos de la enmienda transaccional"), "aprobado")
        self.assertEqual(mt.text_status_for(False, False, "Se vota en los términos de la enmienda transaccional presentada"), "original_transaccional")
        self.assertEqual(mt.text_status_for(False, False, "Se vota en los términos resultantes de la incorporación de la enmienda"), "original_con_enmienda")
        self.assertEqual(mt.text_status_for(False, False, "Se vota en sus términos."), "original_votado")
        self.assertEqual(mt.text_status_for(False, False, ""), "original_votado")

    def test_candidates_by_kind(self) -> None:
        self.assertTrue(mt.candidate_ok("pnl", "162/000014"))
        self.assertFalse(mt.candidate_ok("pnl", "161/000943"))
        self.assertTrue(mt.candidate_ok("mocion", "173/000002"))
        self.assertTrue(mt.candidate_ok("ley", "122/000001"))
        self.assertTrue(mt.candidate_ok("final", "410/000003"))
        self.assertFalse(mt.candidate_ok("ley", "184/009132"))


class TestInitiativePage(unittest.TestCase):
    def test_parse_and_choose(self) -> None:
        page = mt.parse_initiative_page(INITIATIVE_HTML)
        self.assertEqual([b["label"] for b in page["boletines"]], ["Iniciativa", "Enmiendas", "Aprobación por el Pleno"])
        self.assertEqual(page["boletines"][2]["pdf_url"], "https://www.congreso.es/public_oficiales/L15/CONG/BOCG/D/BOCG-15-D-59-C1.PDF")
        self.assertEqual(page["boletines"][2]["page"], 80)
        self.assertEqual(page["diarios"][0]["ds"], "14")
        self.assertEqual(page["vote_paths"], ["Leg15/Sesion013/20231219/Votacion004"])
        self.assertEqual(page["result"], "Aprobado con modificaciones")
        self.assertEqual(
            mt.vote_path("https://www.congreso.es/webpublica/opendata/votaciones/Leg15/Sesion013/20231219/Votacion004/VOT_20231219233105.json"),
            "Leg15/Sesion013/20231219/Votacion004",
        )
        docs = mt.choose_documents(page["boletines"])
        self.assertEqual(docs["original"]["bocg"], "D-20")
        self.assertEqual(docs["approval"]["page"], 80)
        self.assertEqual(docs["amendments"]["page"], 78)
        self.assertEqual(docs["final_stage"]["label"], "Aprobación por el Pleno")


class TestBocgExtraction(unittest.TestCase):
    def test_original_points_are_literal(self) -> None:
        seg = mt.expediente_segment(ORIGINAL_PAGES, "162/000014")
        out = mt.split_points(mt.dispositive_text(seg, "original"))
        self.assertEqual(out["intro"], "El Congreso de los Diputados insta al Gobierno a:")
        self.assertEqual([p["n"] for p in out["points"]], ["1", "2"])
        self.assertEqual(out["points"][0]["text"], "Retomar las negociaciones con Francia sobre el trazado Oloron-Canfranc y su financiación europea.")
        # Nested quotes and lettered sub-points stay inside their point.
        self.assertEqual(out["points"][1]["text"], "Convocar la reunión «cuatripartita» con las regiones: a) Aragón. b) Nueva Aquitania.")

    def test_approval_uses_the_approved_terms_not_the_amendments(self) -> None:
        # Listed on page 79 (index 1) while its expediente header sits on page 78.
        seg = mt.expediente_segment(APPROVAL_PAGES, "162/000014", listed_page_index=1)
        out = mt.split_points(mt.dispositive_text(seg, "approval"))
        self.assertEqual([p["text"] for p in out["points"]], ["Impulsar la modernización de la vía.", "Cooperar con Aragón y Francia."])
        self.assertIsNone(mt.dispositive_text(mt.expediente_segment(ORIGINAL_PAGES, "162/000014"), "approval"))

    def test_unnumbered_motion_is_one_point(self) -> None:
        out = mt.split_points("El Congreso de los Diputados insta al Gobierno a:\nPresentar un plan de vivienda en seis meses.")
        self.assertEqual(out["points"], [{"n": "1", "text": "Presentar un plan de vivienda en seis meses."}])

    def test_footnotes_with_links_are_not_voted_text(self) -> None:
        page = (
            "              162/000099\n"
            "              Exposición de motivos\n"
            "                   Según el INE 4, el paro bajó.\n"
            "                    «El Congreso de los Diputados insta al Gobierno a:\n"
            "                  1. Repatriar el texto del punto uno.\n"
            "                  2. Segundo punto del texto.\n"
            "                   4\n"
            "                      INE: «Encuesta», 2024. Disponible en: https://www.ine.es/x\n"
            "\f"
            "                  3. Tercer punto. reemplazo de lo que dijo alguien en una cita»: https://youtu.be/x\n"
            "                  4. Cuarto punto.»\n"
            "                 Palacio del Congreso de los Diputados, 1 de enero de 2025.\n"
        )
        out = mt.split_points(mt.dispositive_text(mt.expediente_segment(page, "162/000099"), "original"))
        self.assertEqual([p["text"] for p in out["points"]], ["Repatriar el texto del punto uno.", "Segundo punto del texto.", "Tercer punto.", "Cuarto punto."])
        # Lettered sub-points and abbreviations are not mistaken for spilled footnotes.
        self.assertEqual(mt.drop_footnote_spill("Bajar el IVA. b) Subir el art. cinco."), "Bajar el IVA. b) Subir el art. cinco.")

    def test_approval_skips_quotes_in_the_title(self) -> None:
        seg = [
            "              El Pleno ha acordado aprobar con modificaciones la Proposición no de Ley para documentar el",
            "              «bibliocausto español», publicada en el «BOCG. Congreso de los Diputados», en los siguientes términos:",
            "                    «El Congreso de los Diputados insta al Gobierno a:",
            "                   1. Estudiar el «bibliocausto español».",
            "                   2. Reconocer a los libreros.»",
        ]
        out = mt.split_points(mt.dispositive_text(seg, "approval"))
        self.assertEqual([p["n"] for p in out["points"]], ["1", "2"])

    def test_missing_expediente_gives_nothing(self) -> None:
        self.assertEqual(mt.expediente_segment(ORIGINAL_PAGES, "162/999999"), [])


class TestPublishedMotionTexts(unittest.TestCase):
    def test_seed_and_published_docs_are_traceable(self) -> None:
        seed = json.loads(SEED.read_text(encoding="utf-8"))
        self.assertEqual(seed["meta"]["schema_version"], mt.SEED_SCHEMA_VERSION)
        votes = seed["votes"]
        motions = [v for v in votes.values() if v["kind"] in mt.MOTION_KINDS]
        self.assertGreaterEqual(len(motions), 150)
        linked = [v for v in motions if v.get("expediente")]
        self.assertGreaterEqual(len(linked) / len(motions), 0.9)
        for v in linked:
            self.assertEqual(v["match"], "vote_listed_on_initiative_page")
            self.assertRegex(v["expediente"], r"^(162|173)/\d{6}$")
        hl = json.loads(HIGHLIGHTS.read_text(encoding="utf-8"))
        motion_docs = [d for d in hl["docs"].values() if d.get("bullets_basis") == "puntos"]
        self.assertGreaterEqual(len(motion_docs), 120)
        for d in motion_docs:
            self.assertRegex(d["url"], r"^https://www\.congreso\.es/public_oficiales/L15/CONG/BOCG/D/BOCG-15-D-[\w-]+\.PDF#page=\d+$")
            self.assertRegex(d["sha256"], r"^[0-9a-f]{64}$")
            self.assertIn(d["text_status"], mt.TEXT_STATUS_LABELS)
            self.assertTrue(d["points"])


if __name__ == "__main__":
    unittest.main()
