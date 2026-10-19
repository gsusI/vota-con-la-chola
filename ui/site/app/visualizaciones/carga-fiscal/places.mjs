// Community names as they read inside a sentence («del 45 % de Madrid», «de la Comunitat Valenciana»).
const IN_SENTENCE = {
  AN: "Andalucía", AR: "Aragón", AS: "Asturias", IB: "Baleares", CN: "Canarias", CB: "Cantabria", CL: "Castilla y León",
  CM: "Castilla-La Mancha", CT: "Cataluña", VC: "la Comunitat Valenciana", EX: "Extremadura", GA: "Galicia", MD: "Madrid",
  MC: "Murcia", RI: "La Rioja", PV: "el País Vasco", NC: "Navarra",
};

export const place = (row) => IN_SENTENCE[row.code] || row.name;
export const placeTitle = (row) => {
  const name = place(row);
  return name.charAt(0).toUpperCase() + name.slice(1);
};
