// src/utils/index.js
// Shared small utilities for display and FK endpoint selection.

export function getDisplayLabel(obj) {
  if (!obj) return "";
  if (typeof obj === "string") return obj;
  return (
    (obj.name && String(obj.name)) ||
    (obj.code && String(obj.code)) ||
    (obj.hsn_code && String(obj.hsn_code)) ||
    (obj.description && String(obj.description)) ||
    (obj.__str__ && String(obj.__str__)) ||
    ""
  );
}

/*
  Map known field keys to API endpoints. Extend this map for your app.
  Returns subset for provided schema (object of fields).
*/
const KNOWN_FK_MAP = {
  hsn_code: "/masters/hs-codes/",
  head_norm: "/masters/head-norms/",
  norm_class: "/masters/sion-classes/",
  company: "/masters/companies/",
  port: "/masters/ports/",
};

/*
  Given a schema object (or list of field names), return only the endpoints
  that match schema fields. Accepts:
    - schema: object mapping field -> cfg
    - or array of field names
*/
export function getFkEndpoints(schemaOrFields) {
  const keys =
    Array.isArray(schemaOrFields) ? schemaOrFields : (schemaOrFields && typeof schemaOrFields === "object"
      ? Object.keys(schemaOrFields)
      : []);
  const out = {};
  keys.forEach((k) => {
    if (KNOWN_FK_MAP[k]) out[k] = KNOWN_FK_MAP[k];
  });
  return out;
}

export default {
  getDisplayLabel,
  getFkEndpoints,
};
