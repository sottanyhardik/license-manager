// Shared cache used by AsyncSelectField to avoid duplicate FK detail
// fetches. Each form page renders many AsyncSelectField instances; without
// this, a license with 10 import rows × N items each would hammer the
// `/masters/hs-codes/<id>/` and `/masters/item-names/<id>/` endpoints with
// dozens of identical GETs.
//
// _fkDetailCache : url -> raw response data
// _fkInFlight    : url -> Promise<data> (coalesces concurrent requests)
export const _fkDetailCache = new Map();
export const _fkInFlight = new Map();

export function primeFkDetailCache(endpoint, item) {
    if (!endpoint || !item || item.id == null) return;
    const base = endpoint.startsWith('/api/') ? endpoint.substring(5) : endpoint;
    const baseEndpoint = base.split('?')[0];
    _fkDetailCache.set(`${baseEndpoint}${item.id}/`, item);
}
