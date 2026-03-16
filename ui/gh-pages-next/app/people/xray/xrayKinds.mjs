export const XRAY_KIND_ORDER = [
  "party",
  "institution",
  "ambito",
  "territorio",
  "cargo",
];

export const XRAY_KIND_META = {
  party: {
    kind: "party",
    label: "Partido",
    pluralLabel: "Partidos",
    description: "Personas vinculadas a cada partido por sus mandatos.",
    itemLabel: "Partido",
    href: "/people/xray/party/",
  },
  institution: {
    kind: "institution",
    label: "Institución",
    pluralLabel: "Instituciones",
    description: "Personas con mandatos en cada institución.",
    itemLabel: "Institución",
    href: "/people/xray/institution/",
  },
  ambito: {
    kind: "ambito",
    label: "Ámbito",
    pluralLabel: "Ámbitos",
    description: "Personas agrupadas por ámbito territorial-administrativo.",
    itemLabel: "Ámbito",
    href: "/people/xray/ambito/",
  },
  territorio: {
    kind: "territorio",
    label: "Territorio",
    pluralLabel: "Territorios",
    description: "Personas vinculadas a cada territorio.",
    itemLabel: "Territorio",
    href: "/people/xray/territorio/",
  },
  cargo: {
    kind: "cargo",
    label: "Cargo",
    pluralLabel: "Cargos",
    description: "Personas con cada tipo de cargo en mandatos.",
    itemLabel: "Cargo",
    href: "/people/xray/cargo/",
  },
};

export const XRAY_KIND_LINKS = XRAY_KIND_ORDER.map((kind) => ({
  kind,
  label: XRAY_KIND_META[kind].pluralLabel,
  href: XRAY_KIND_META[kind].href,
}));
