import { useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import { Dialog, DialogContent } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Loader2, Plus, Save, Trash2, Target, Wand2 } from 'lucide-react';
import {
    fetchLicense,
    fetchItemPlans,
    bulkUpsertItemPlans,
    fetchNormPrefill,
} from '../../services/api/licenseApi';

/**
 * LicensePlanningPanel
 *
 * A license is planned per PRODUCT: import items are grouped by description
 * (matching the backend `plan_grouping.plan_group_key`) and their quantities
 * summed, so the user plans against the product's total quantity across serial
 * numbers. Each group can be split into named lines (WPC / SWP / …), each with
 * quantity, unit price and CIF ($) with 3-way auto-calc:
 *   - qty & unit price   → cif = qty × unit price
 *   - cif & unit price   → qty = cif ÷ unit price (capped at available)
 *   - qty & cif          → unit price = cif ÷ qty (max 2 dp)
 *
 * A group's plan is saved against its representative import item (lowest serial).
 */

let _sk = 0;
const nextKey = () => `s${++_sk}`;
const num = (v) => parseFloat(v) || 0;
const round2 = (x) => Math.round((x + Number.EPSILON) * 100) / 100;
const fmt2 = (x) => (x ? String(round2(x)) : '');
const fmt3 = (x) => (x ? String(Math.round((x + Number.EPSILON) * 1000) / 1000) : '');

const emptySplit = () => ({ key: nextKey(), item_name: '', planned_quantity: '', unit_price: '', planned_cif_fc: '' });

// Group key — must match backend apps/license/services/plan_grouping.plan_group_key.
const groupKeyOf = (desc, itemNames) => {
    const d = (desc || '').trim();
    if (d) return d.toUpperCase();
    const names = (itemNames || []).map((n) => n.name).sort().join(', ');
    if (names) return 'N:' + names.toUpperCase();
    return null; // caller falls back to a per-item key
};

export default function LicensePlanningPanel({
    show,
    onHide,
    licenseId,
    licenseNumber,
    balanceCif = 0,
    onSaved = () => {},
}) {
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [prefilling, setPrefilling] = useState(false);
    // groups: [{ id(rep), description, serials[], memberIds[], total_quantity,
    //            available_quantity, itemNames[], splits[] }]
    const [groups, setGroups] = useState([]);
    const [poolBalance, setPoolBalance] = useState(Number(balanceCif) || 0);

    useEffect(() => {
        if (!show || !licenseId) return;
        let cancelled = false;

        (async () => {
            setLoading(true);
            try {
                const [license, plans] = await Promise.all([
                    fetchLicense(licenseId),
                    fetchItemPlans(licenseId),
                ]);
                if (cancelled) return;

                const planList = Array.isArray(plans) ? plans : (plans?.results || []);
                const splitsByItem = {};
                planList.forEach((p) => {
                    (splitsByItem[p.import_item] ||= []).push({
                        key: nextKey(),
                        item_name: p.item_name ? String(p.item_name) : '',
                        planned_quantity: p.planned_quantity != null ? String(p.planned_quantity) : '',
                        unit_price: p.unit_price != null ? String(p.unit_price) : '',
                        planned_cif_fc: p.planned_cif_fc != null ? String(p.planned_cif_fc) : '',
                    });
                });

                setPoolBalance(Number(license?.get_balance_cif ?? license?.balance_cif ?? balanceCif ?? 0));

                const itemList = license?.import_license || license?.import_license_read || [];

                // Group import items by description (matching the backend key).
                const byKey = {};
                itemList.forEach((it) => {
                    const itemNames = (it.items_detail || []).map((n) => ({ id: n.id, name: n.name }));
                    const key = groupKeyOf(it.product_description || it.description, itemNames) || `ID:${it.id}`;
                    const g = (byKey[key] ||= {
                        key,
                        description: it.product_description || it.description || `S.No ${it.serial_number}`,
                        serials: [],
                        members: [],
                        total_quantity: 0,
                        available_quantity: 0,
                        itemNames: [],
                        _nameIds: new Set(),
                        hsCodes: [],
                        _hsSet: new Set(),
                    });
                    const hs = it.hs_code_label || it.hs_code_detail?.hs_code;
                    if (hs && !g._hsSet.has(hs)) { g._hsSet.add(hs); g.hsCodes.push(hs); }
                    g.serials.push(it.serial_number);
                    g.members.push({ id: it.id, serial: it.serial_number });
                    g.total_quantity += Number(it.quantity || 0);
                    g.available_quantity += Number(it.available_quantity || 0);
                    itemNames.forEach((n) => {
                        if (!g._nameIds.has(n.id)) { g._nameIds.add(n.id); g.itemNames.push(n); }
                    });
                });

                const built = (Object.values(byKey) as any[]).map((g) => {
                    // Representative = lowest serial member.
                    const rep = g.members.slice().sort((a, b) => a.serial - b.serial)[0];
                    const memberIds = g.members.map((m) => m.id);
                    // Existing plan splits: any member (they are stored on the rep).
                    let splits = [];
                    memberIds.forEach((mid) => { if (splitsByItem[mid]) splits = splits.concat(splitsByItem[mid]); });
                    return {
                        id: rep.id,
                        description: g.description,
                        serials: g.serials.sort((a, b) => a - b),
                        memberIds,
                        total_quantity: g.total_quantity,
                        available_quantity: g.available_quantity,
                        itemNames: g.itemNames,
                        hsCodes: g.hsCodes,
                        splits: splits.length ? splits : [emptySplit()],
                    };
                });
                setGroups(built);
            } catch (err) {
                console.error('Failed to load planning data', err);
                toast.error('Failed to load planning data');
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();

        return () => { cancelled = true; };
    }, [show, licenseId, balanceCif]);

    const updateGroup = (repId, updater) =>
        setGroups((prev) => prev.map((g) => (g.id === repId ? updater(g) : g)));

    const addSplit = (repId) =>
        updateGroup(repId, (g) => ({ ...g, splits: [...g.splits, emptySplit()] }));

    const removeSplit = (repId, key) =>
        updateGroup(repId, (g) => ({
            ...g,
            splits: g.splits.length > 1 ? g.splits.filter((s) => s.key !== key) : g.splits,
        }));

    // 3-way auto-calc within a split, capped at the group's remaining available.
    const changeSplit = (repId, key, field, value) =>
        updateGroup(repId, (g) => {
            const otherQty = g.splits.reduce((s, sp) => s + (sp.key === key ? 0 : num(sp.planned_quantity)), 0);
            const availLeft = Math.max(g.available_quantity - otherQty, 0);
            const splits = g.splits.map((sp) => {
                if (sp.key !== key) return sp;
                let q = num(sp.planned_quantity), up = num(sp.unit_price), cif = num(sp.planned_cif_fc);
                if (field === 'planned_quantity') {
                    q = num(value);
                    if (up > 0) cif = q * up;
                    else if (cif > 0 && q > 0) up = round2(cif / q);
                } else if (field === 'unit_price') {
                    up = num(value);
                    if (q > 0) cif = q * up;
                    else if (cif > 0 && up > 0) q = Math.min(cif / up, availLeft);
                } else if (field === 'planned_cif_fc') {
                    cif = num(value);
                    if (up > 0) q = Math.min(cif / up, availLeft);
                    else if (q > 0) up = round2(cif / q);
                } else if (field === 'item_name') {
                    return { ...sp, item_name: value };
                }
                return {
                    ...sp,
                    planned_quantity: field === 'planned_quantity' ? value : fmt3(q),
                    unit_price: field === 'unit_price' ? value : fmt2(up),
                    planned_cif_fc: field === 'planned_cif_fc' ? value : fmt2(cif),
                };
            });
            return { ...g, splits };
        });

    const plannedCifTotal = useMemo(
        () => groups.reduce((sum, g) => sum + g.splits.reduce((s, sp) => s + num(sp.planned_cif_fc), 0), 0),
        [groups],
    );
    const cifRemaining = Number(poolBalance) - plannedCifTotal;
    const cifOver = cifRemaining < 0;
    const groupQtySum = (g) => g.splits.reduce((s, sp) => s + num(sp.planned_quantity), 0);

    const handlePrefill = async () => {
        setPrefilling(true);
        try {
            const { norm, plan } = await fetchNormPrefill(licenseId);
            if (!norm) { toast.error('This license has no E1/E5/E132 norm to plan from'); return; }
            let filled = 0;
            setGroups((prev) => prev.map((g) => {
                // Sum the norm plan across the group's member items.
                let q = 0, c = 0;
                g.memberIds.forEach((mid) => {
                    const p = plan?.[String(mid)];
                    if (p) { q += Number(p.planned_quantity || 0); c += Number(p.planned_cif || 0); }
                });
                if (q > 0 || c > 0) {
                    filled += 1;
                    return {
                        ...g,
                        splits: [{
                            key: nextKey(), item_name: '',
                            planned_quantity: q ? fmt3(q) : '',
                            unit_price: q ? String(round2(c / q)) : '',
                            planned_cif_fc: c ? fmt2(c) : '',
                        }],
                    };
                }
                return g;
            }));
            toast.success(`Prefilled ${filled} product(s) from ${norm} plan — review and Save`);
        } catch (e) {
            toast.error('Failed to compute norm plan');
        } finally {
            setPrefilling(false);
        }
    };

    const handleSave = async () => {
        const lines = [];
        for (const g of groups) {
            for (const sp of g.splits) {
                if (num(sp.planned_quantity) > 0 || num(sp.planned_cif_fc) > 0) {
                    lines.push({
                        import_item: g.id,          // representative import item
                        item_name: sp.item_name ? Number(sp.item_name) : null,
                        planned_quantity: num(sp.planned_quantity),
                        unit_price: num(sp.unit_price),
                        planned_cif_fc: num(sp.planned_cif_fc),
                    });
                }
            }
        }
        if (cifOver) { toast.error('Planned CIF total exceeds the license balance'); return; }
        const bad = groups.find((g) => groupQtySum(g) > g.available_quantity + 1e-6);
        if (bad) { toast.error(`${bad.description}: planned qty exceeds available`); return; }

        setSaving(true);
        try {
            await bulkUpsertItemPlans(licenseId, lines);
            toast.success('Plan saved');
            onSaved();
            onHide?.();
        } catch (err) {
            const data = err?.response?.data;
            const msg = data?.error || (data?.errors ? JSON.stringify(data.errors) : null) || 'Failed to save plan';
            toast.error(msg);
        } finally {
            setSaving(false);
        }
    };

    return (
        <Dialog open={show} onOpenChange={(o) => { if (!o) onHide?.(); }}>
            <DialogContent className="max-w-4xl">
                <div className="flex items-center justify-between mb-3 pr-8">
                    <div className="flex items-center gap-2 text-base font-semibold">
                        <Target className="size-5 text-primary" aria-hidden="true" />
                        Plan utilization — {licenseNumber}
                    </div>
                    <Button variant="outline" size="sm" onClick={handlePrefill} disabled={loading || prefilling}>
                        {prefilling ? <Loader2 className="size-4 animate-spin mr-1" /> : <Wand2 className="size-4 mr-1" />}
                        Prefill from norm
                    </Button>
                </div>

                <div className="mb-3 rounded-md border border-border bg-muted/40 px-3 py-2 text-sm flex items-center justify-between">
                    <span>Balance CIF: <b>{Number(poolBalance).toFixed(2)}</b></span>
                    <span>Planned: <b>{plannedCifTotal.toFixed(2)}</b></span>
                    <span className={cifOver ? 'text-red-600 font-semibold' : 'text-green-600 font-semibold'}>
                        {cifOver ? 'Over by ' : 'Remaining '}{Math.abs(cifRemaining).toFixed(2)}
                    </span>
                </div>

                {loading ? (
                    <div className="flex items-center justify-center py-10 text-muted-foreground">
                        <Loader2 className="size-5 animate-spin mr-2" /> Loading items…
                    </div>
                ) : (
                    <div className="max-h-[60vh] overflow-auto space-y-3">
                        {groups.map((g) => {
                            const qtySum = groupQtySum(g);
                            const qtyOver = qtySum > g.available_quantity + 1e-6;
                            return (
                                <div key={g.id} className="rounded-md border border-border p-3">
                                    <div className="flex items-center justify-between mb-2">
                                        <div className="text-sm font-medium">
                                            {g.description}
                                            <span className="text-xs text-muted-foreground ml-2">S.No {g.serials.join(', ')}</span>
                                            {g.hsCodes?.length > 0 && (
                                                <span className="text-xs text-muted-foreground ml-2">HSN {g.hsCodes.join(', ')}</span>
                                            )}
                                        </div>
                                        <div className="text-xs text-muted-foreground">
                                            Total {g.total_quantity.toFixed(3)} · Avail {g.available_quantity.toFixed(3)} ·{' '}
                                            <span className={qtyOver ? 'text-red-600 font-semibold' : ''}>Planned {qtySum.toFixed(3)}</span>
                                        </div>
                                    </div>

                                    <table className="w-full text-sm">
                                        <thead>
                                            <tr className="text-left text-xs text-muted-foreground">
                                                <th scope="col" className="pb-1 pr-2 font-medium">Item name</th>
                                                <th scope="col" className="pb-1 pr-2 font-medium text-right">Qty</th>
                                                <th scope="col" className="pb-1 pr-2 font-medium text-right">Unit price</th>
                                                <th scope="col" className="pb-1 pr-2 font-medium text-right">CIF ($)</th>
                                                <th scope="col" className="pb-1 w-8"></th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {g.splits.map((sp) => (
                                                <tr key={sp.key}>
                                                    <td className="py-1 pr-2">
                                                        <select
                                                            value={sp.item_name}
                                                            onChange={(e) => changeSplit(g.id, sp.key, 'item_name', e.target.value)}
                                                            className="h-8 w-full rounded-md border border-input bg-background px-2 text-sm"
                                                        >
                                                            <option value="">—</option>
                                                            {g.itemNames.map((n) => (
                                                                <option key={n.id} value={n.id}>{n.name}</option>
                                                            ))}
                                                        </select>
                                                    </td>
                                                    <td className="py-1 pr-2">
                                                        <Input type="number" min="0" step="0.001" value={sp.planned_quantity}
                                                            onChange={(e) => changeSplit(g.id, sp.key, 'planned_quantity', e.target.value)}
                                                            className="h-8 w-24 text-right" />
                                                    </td>
                                                    <td className="py-1 pr-2">
                                                        <Input type="number" min="0" step="0.01" value={sp.unit_price}
                                                            onChange={(e) => changeSplit(g.id, sp.key, 'unit_price', e.target.value)}
                                                            className="h-8 w-24 text-right" />
                                                    </td>
                                                    <td className="py-1 pr-2">
                                                        <Input type="number" min="0" step="0.01" value={sp.planned_cif_fc}
                                                            onChange={(e) => changeSplit(g.id, sp.key, 'planned_cif_fc', e.target.value)}
                                                            className="h-8 w-28 text-right" />
                                                    </td>
                                                    <td className="py-1 text-center">
                                                        <button onClick={() => removeSplit(g.id, sp.key)} disabled={g.splits.length <= 1}
                                                            className="text-muted-foreground hover:text-red-600 disabled:opacity-30" title="Remove split">
                                                            <Trash2 className="size-4" />
                                                        </button>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>

                                    <button onClick={() => addSplit(g.id)}
                                        className="mt-2 flex items-center gap-1 text-xs font-medium text-primary hover:underline">
                                        <Plus className="size-3.5" /> Add split
                                    </button>
                                </div>
                            );
                        })}
                        {groups.length === 0 && (
                            <div className="py-6 text-center text-muted-foreground">No import items</div>
                        )}
                    </div>
                )}

                <div className="mt-4 flex justify-end gap-2">
                    <Button variant="outline" onClick={() => onHide?.()} disabled={saving}>Cancel</Button>
                    <Button onClick={handleSave} disabled={saving || loading || cifOver}>
                        {saving ? <Loader2 className="size-4 animate-spin mr-1" /> : <Save className="size-4 mr-1" />}
                        Save plan
                    </Button>
                </div>
            </DialogContent>
        </Dialog>
    );
}
