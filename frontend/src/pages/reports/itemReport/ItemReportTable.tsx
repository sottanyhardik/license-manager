import Select from "react-select";
import { Card, CardContent } from "@/components/ui/card";
import ConditionBadge from "@/components/ConditionBadge";
import { openAuthedFile } from "@/utils/documentDownload";
import { formatDate } from "@/utils/dateFormatter";
import { clickable } from "@/utils/clickable";
import { Check, Pencil, ShieldCheck, X } from "lucide-react";
import type { ItemReportEditingCell } from "./useItemReportData";
import type { SelectOption } from "./useItemReportFilters";

export interface ItemReportTableProps {
    items: any[];
    /**
     * Items the totals row sums over — defaults to `items`. Pass the full,
     * unpaginated filtered set here when `items` itself is just the current
     * page, so totals always reflect "after filtering", not "on this page".
     */
    totalsItems?: any[];
    /** Sr No continues from this value — set to the count of rows on prior pages when paginating. */
    startSrNo?: number;
    /**
     * 'editable' (Item Report) renders the Item Name cell as a multiselect
     * that PATCHes `license-items/{id}/` on change. 'readonly' (Planned
     * Report) renders the row's single `planned_item_name` as plain text.
     * Nothing else in the table depends on this.
     */
    itemNameMode: "editable" | "readonly";
    /** Required when itemNameMode is 'editable'. */
    itemNameOptions?: SelectOption[];
    /** Required when itemNameMode is 'editable'. */
    onItemNamesChange?: (item: any, selected: { value: unknown; label: string }[] | null) => void;

    editingCell: ItemReportEditingCell;
    editValue: string;
    onEditValueChange: (value: string) => void;
    onStartEdit: (itemId: unknown, field: "notes" | "condition_sheet", currentValue: string) => void;
    onCancelEdit: () => void;
    onSaveEdit: (item: any) => void;
}

function formatQty(value: unknown): string {
    return Number(value || 0).toLocaleString('en-IN', { minimumFractionDigits: 3, maximumFractionDigits: 3 });
}

function formatCif(value: unknown): string {
    return Number(value || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/**
 * Grouped (one rowSpan block per license), sticky-header report table shared
 * by Item Report and Planned Report. Column order matches the Excel export
 * exactly (see item_report.py's export_to_excel): the business-required
 * columns (Sr No .. Plan CIF) followed by the pre-existing extra columns
 * (Balance CIF, Is Restricted, Notes, Condition Sheet, Transfer Status).
 */
export default function ItemReportTable({
    items, totalsItems, startSrNo = 0, itemNameMode, itemNameOptions = [], onItemNamesChange,
    editingCell, editValue, onEditValueChange, onStartEdit, onCancelEdit, onSaveEdit,
}: ItemReportTableProps) {
    const totalsSource = totalsItems ?? items;
    // Group items by license_id
    const groupedByLicense: Record<string, any[]> = {};
    items.forEach(item => {
        if (!groupedByLicense[item.license_id]) {
            groupedByLicense[item.license_id] = [];
        }
        groupedByLicense[item.license_id].push(item);
    });

    let srNo = startSrNo;

    return (
        <Card>
            <CardContent className="p-0">
                <div className="overflow-x-auto">
                    <table className="table table-hover table-sm mb-0"
                           style={{tableLayout: 'auto', minWidth: '1600px'}}>
                        <thead style={{position: 'sticky', top: 0, zIndex: 10}}>
                        <tr className="table-light">
                            <th scope="col" className="text-center" style={{
                                position: 'sticky',
                                left: 0,
                                zIndex: 11,
                                backgroundColor: 'var(--tb-sunken)',
                                minWidth: '60px'
                            }}>Sr No
                            </th>
                            <th scope="col" style={{
                                position: 'sticky',
                                left: '60px',
                                zIndex: 11,
                                backgroundColor: 'var(--tb-sunken)',
                                minWidth: '150px'
                            }}>License No
                            </th>
                            <th scope="col" style={{minWidth: '120px'}}>License Date
                            </th>
                            <th scope="col" style={{
                                position: 'sticky',
                                left: '210px',
                                zIndex: 11,
                                backgroundColor: 'var(--tb-sunken)',
                                minWidth: '140px'
                            }}>License Expiry Date
                            </th>
                            <th scope="col" style={{minWidth: '120px'}}>Ledger Date</th>
                            <th scope="col" style={{minWidth: '200px'}}>Exporter Name</th>
                            <th scope="col" style={{minWidth: '100px'}}>Serial Number</th>
                            <th scope="col" className="text-center" style={{minWidth: '90px'}}>Condition</th>
                            <th scope="col" style={{minWidth: '100px'}}>HSN Code</th>
                            <th scope="col" style={{minWidth: '250px'}}>Product Description</th>
                            <th scope="col" style={{minWidth: '200px'}}>Item Name</th>
                            <th scope="col" className="text-right" style={{minWidth: '140px'}}>Available Quantity</th>
                            <th scope="col" className="text-right" style={{minWidth: '110px'}}>Unit Price</th>
                            <th scope="col" className="text-right" style={{minWidth: '140px'}}>Available Balance</th>
                            <th scope="col" className="text-right" style={{minWidth: '120px'}}>Plan Qty</th>
                            <th scope="col" className="text-right" style={{minWidth: '120px'}}>Plan CIF</th>
                            <th scope="col" className="text-right" style={{
                                position: 'sticky',
                                left: '350px',
                                zIndex: 11,
                                backgroundColor: 'var(--tb-sunken)',
                                minWidth: '140px',
                                boxShadow: '3px 0 8px rgba(0,0,0,0.15)',
                                borderRight: '2px solid var(--tb-border)'
                            }}>Balance CIF</th>
                            <th scope="col" className="text-center" style={{minWidth: '120px'}}>Is Restricted</th>
                            <th scope="col" style={{minWidth: '200px'}}>Notes</th>
                            <th scope="col" style={{minWidth: '200px'}}>Condition Sheet</th>
                            <th scope="col" style={{minWidth: '250px'}}>Transfer Status</th>
                        </tr>
                        </thead>
                        <tbody>
                        {Object.values(groupedByLicense).map((licenseItems: any[]) => {
                            const firstItem = licenseItems[0];
                            const rowSpan = licenseItems.length;

                            return licenseItems.map((item, itemIdx) => {
                                srNo++;
                                const isFirstRow = itemIdx === 0;

                                return (
                                    <tr key={item.id} style={{
                                        borderBottom: itemIdx === licenseItems.length - 1 ? '2px solid var(--tb-border)' : '',
                                        verticalAlign: 'middle'
                                    }}>
                                        {isFirstRow && (
                                            <>
                                                <td className="text-center" rowSpan={rowSpan}
                                                    style={{
                                                        position: 'sticky',
                                                        left: 0,
                                                        zIndex: 9,
                                                        verticalAlign: 'middle',
                                                        backgroundColor: 'var(--tb-sunken)',
                                                        fontWeight: '500'
                                                    }}>{srNo - itemIdx}</td>
                                                <td rowSpan={rowSpan} style={{
                                                    position: 'sticky',
                                                    left: '60px',
                                                    zIndex: 9,
                                                    verticalAlign: 'middle',
                                                    backgroundColor: 'var(--tb-sunken)',
                                                    fontWeight: '600'
                                                }}>
                                                    <div
                                                        className="flex items-center justify-between">
                                                        <span>{firstItem.license_number}</span>
                                                        <button
                                                            className="ml-2 flex items-center gap-1.5 rounded border border-border bg-card px-2 py-1 text-xs font-medium text-muted-foreground cursor-pointer hover:bg-muted"
                                                            style={{
                                                                padding: '2px 8px',
                                                                fontSize: 12
                                                            }}
                                                            onClick={() => {
                                                                openAuthedFile(`licenses/${firstItem.license_id}/merged-documents/`);
                                                            }}
                                                            title="View/Download merged documents"
                                                        >
                                                            Docs
                                                        </button>
                                                    </div>
                                                </td>
                                                <td rowSpan={rowSpan} style={{
                                                    verticalAlign: 'middle',
                                                    backgroundColor: 'var(--tb-sunken)'
                                                }}>{formatDate(firstItem.license_date)}</td>
                                                <td rowSpan={rowSpan} style={{
                                                    position: 'sticky',
                                                    left: '210px',
                                                    zIndex: 9,
                                                    verticalAlign: 'middle',
                                                    backgroundColor: 'var(--tb-sunken)'
                                                }}>{formatDate(firstItem.license_expiry_date)}</td>
                                                <td rowSpan={rowSpan} style={{
                                                    verticalAlign: 'middle',
                                                    backgroundColor: 'var(--tb-sunken)'
                                                }}>{formatDate(firstItem.ledger_date)}</td>
                                                <td rowSpan={rowSpan} style={{
                                                    verticalAlign: 'middle',
                                                    backgroundColor: 'var(--tb-sunken)'
                                                }}>{firstItem.exporter_name || '-'}</td>
                                            </>
                                        )}
                                        <td style={{verticalAlign: 'middle'}}>{item.serial_number}</td>
                                        <td className="text-center" style={{verticalAlign: 'middle'}}>
                                            <ConditionBadge type={item.condition_type} size="xs" />
                                        </td>
                                        <td style={{verticalAlign: 'middle'}}>{item.hs_code || '-'}</td>
                                        <td style={{verticalAlign: 'middle'}}>{item.product_description || '-'}</td>
                                        <td>
                                            {itemNameMode === 'editable' ? (
                                                <Select
                                                    isMulti
                                                    value={(item.item_names || []).map((i: any) => ({
                                                        value: i.id,
                                                        label: i.name
                                                    }))}
                                                    onChange={(selected) => onItemNamesChange?.(item, selected as any)}
                                                    options={itemNameOptions}
                                                    placeholder="Select item names..."
                                                    className="basic-multi-select"
                                                    classNamePrefix="select"
                                                    styles={{
                                                        control: (base) => ({
                                                            ...base,
                                                            minHeight: '32px',
                                                            fontSize: 14
                                                        })
                                                    }}
                                                />
                                            ) : (
                                                <span>{item.planned_item_name || '-'}</span>
                                            )}
                                        </td>
                                        <td className="text-right">{formatQty(item.available_quantity)}</td>
                                        <td className="text-right">{formatCif(item.unit_price)}</td>
                                        {isFirstRow && (
                                            <td className="text-right text-success font-semibold"
                                                rowSpan={rowSpan} style={{
                                                verticalAlign: 'middle',
                                                backgroundColor: 'var(--tb-sunken)'
                                            }}>{formatCif(firstItem.available_balance)}</td>
                                        )}
                                        <td className="text-right" title={(item.planned_splits || []).map((s: any) => `${s.item_name || '—'}: ${Number(s.planned_quantity).toFixed(3)} @ ${Number(s.unit_price).toFixed(2)} = ${Number(s.planned_cif_fc).toFixed(2)}`).join('\n')}>
                                            {Number(item.planned_quantity || 0) > 0 ? formatQty(item.planned_quantity) : '-'}
                                        </td>
                                        <td className="text-right">
                                            {Number(item.planned_cif || 0) > 0 ? formatCif(item.planned_cif) : '-'}
                                        </td>
                                        {isFirstRow && (
                                            <>
                                                <td className="text-right text-primary font-semibold"
                                                    rowSpan={rowSpan} style={{
                                                    position: 'sticky',
                                                    left: '350px',
                                                    zIndex: 9,
                                                    verticalAlign: 'middle',
                                                    backgroundColor: 'var(--tb-sunken)',
                                                    boxShadow: '3px 0 8px rgba(0,0,0,0.15)',
                                                    borderRight: '2px solid var(--tb-border)'
                                                }}>{formatCif(firstItem.balance_cif)}</td>
                                                <td className="text-center" rowSpan={rowSpan}
                                                    style={{
                                                        verticalAlign: 'middle',
                                                        backgroundColor: 'var(--tb-sunken)'
                                                    }}>
                                                    {/* Restriction is derived from condition_type (licence's
                                                        condition sheet) — read-only display. */}
                                                    {firstItem.condition_type
                                                        ? <ConditionBadge type={firstItem.condition_type} />
                                                        : <span className="badge bg-success">
                                                              <ShieldCheck className="size-4" aria-hidden="true" />Open
                                                          </span>}
                                                </td>
                                                <td rowSpan={rowSpan} style={{
                                                    verticalAlign: 'middle',
                                                    backgroundColor: 'var(--tb-sunken)'
                                                }}>
                                                    {editingCell?.itemId === firstItem.id && editingCell?.field === 'notes' ? (
                                                        <div className="flex gap-1">
                                                            <input
                                                                type="text"
                                                                className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none focus-visible:border-ring"
                                                                value={editValue}
                                                                onChange={(e) => onEditValueChange(e.target.value)}
                                                                autoFocus
                                                            />
                                                            <button
                                                                className="flex items-center gap-1.5 rounded bg-success px-2 py-1 text-xs font-medium text-white cursor-pointer"
                                                                onClick={() => onSaveEdit(firstItem)}
                                                            >
                                                                <Check className="size-4" aria-hidden="true" />
                                                            </button>
                                                            <button
                                                                className="flex items-center gap-1.5 rounded border border-border bg-card px-2 py-1 text-xs font-medium text-muted-foreground cursor-pointer hover:bg-muted"
                                                                onClick={onCancelEdit}
                                                            >
                                                                <X className="size-4" aria-hidden="true" />
                                                            </button>
                                                        </div>
                                                    ) : (
                                                        <div
                                                            className="flex items-center justify-between"
                                                            style={{cursor: 'pointer'}}
                                                            {...clickable(() => onStartEdit(firstItem.id, 'notes', firstItem.notes))}
                                                        >
                                                            <span>{firstItem.notes || '-'}</span>
                                                            <Pencil className="size-4" aria-hidden="true" />
                                                        </div>
                                                    )}
                                                </td>
                                                <td rowSpan={rowSpan} style={{
                                                    verticalAlign: 'middle',
                                                    backgroundColor: 'var(--tb-sunken)'
                                                }}>
                                                    {editingCell?.itemId === firstItem.id && editingCell?.field === 'condition_sheet' ? (
                                                        <div className="flex gap-1">
                                                            <input
                                                                type="text"
                                                                className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none focus-visible:border-ring"
                                                                value={editValue}
                                                                onChange={(e) => onEditValueChange(e.target.value)}
                                                                autoFocus
                                                            />
                                                            <button
                                                                className="flex items-center gap-1.5 rounded bg-success px-2 py-1 text-xs font-medium text-white cursor-pointer"
                                                                onClick={() => onSaveEdit(firstItem)}
                                                            >
                                                                <Check className="size-4" aria-hidden="true" />
                                                            </button>
                                                            <button
                                                                className="flex items-center gap-1.5 rounded border border-border bg-card px-2 py-1 text-xs font-medium text-muted-foreground cursor-pointer hover:bg-muted"
                                                                onClick={onCancelEdit}
                                                            >
                                                                <X className="size-4" aria-hidden="true" />
                                                            </button>
                                                        </div>
                                                    ) : (
                                                        <div
                                                            className="flex items-center justify-between"
                                                            style={{cursor: 'pointer'}}
                                                            {...clickable(() => onStartEdit(firstItem.id, 'condition_sheet', firstItem.condition_sheet))}
                                                        >
                                                            <span>{firstItem.condition_sheet || '-'}</span>
                                                            <Pencil className="size-4" aria-hidden="true" />
                                                        </div>
                                                    )}
                                                </td>
                                                <td rowSpan={rowSpan} style={{
                                                    verticalAlign: 'middle',
                                                    backgroundColor: 'var(--tb-sunken)',
                                                    fontSize: 13.5,
                                                    lineHeight: '1.4'
                                                }}>
                                                    {firstItem.latest_transfer ? (
                                                        <div>{firstItem.latest_transfer}</div>
                                                    ) : (
                                                        <span className="text-muted-foreground">-</span>
                                                    )}
                                                </td>
                                            </>
                                        )}
                                    </tr>
                                );
                            });
                        })}
                        </tbody>
                        <tfoot style={{position: 'sticky', bottom: 0, zIndex: 10}}>
                        <tr className="table-secondary font-bold">
                            <td colSpan={11} className="text-right" style={{
                                position: 'sticky',
                                left: 0,
                                zIndex: 11,
                                backgroundColor: 'var(--tb-border)',
                                fontWeight: '600'
                            }}>
                                Total:
                            </td>
                            <td className="text-right" style={{fontWeight: '600'}}>
                                {formatQty(totalsSource.reduce((sum, item) => sum + (item.available_quantity || 0), 0))}
                            </td>
                            <td></td>
                            <td className="text-right text-success" style={{fontWeight: '600'}}>
                                {(() => {
                                    // Available Balance is license-level (repeated per item) —
                                    // sum once per license, not once per raw row.
                                    const uniqueLicenses: Record<string, number> = {};
                                    totalsSource.forEach((item: any) => {
                                        if (!(item.license_id in uniqueLicenses)) {
                                            uniqueLicenses[item.license_id] = item.available_balance || 0;
                                        }
                                    });
                                    return formatCif(Object.values(uniqueLicenses).reduce((sum: number, val: number) => sum + val, 0));
                                })()}
                            </td>
                            <td className="text-right" style={{fontWeight: '600'}}>
                                {formatQty(totalsSource.reduce((sum, item) => sum + (item.planned_quantity || 0), 0))}
                            </td>
                            <td className="text-right" style={{fontWeight: '600'}}>
                                {formatCif(totalsSource.reduce((sum, item) => sum + (item.planned_cif || 0), 0))}
                            </td>
                            <td colSpan={5}></td>
                        </tr>
                        </tfoot>
                    </table>
                </div>
            </CardContent>
        </Card>
    );
}
