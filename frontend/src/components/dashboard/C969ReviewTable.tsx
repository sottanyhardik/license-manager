import { Link } from "react-router-dom";

import type { C969LinkReview, SectionError } from "@/pages/dashboardContract";
import { isSectionError } from "@/pages/dashboardContract";
import { licenceEditPath } from "./dashboardLinks";
import { formatCount } from "./formatters";
import DashboardSection from "./DashboardSection";

type C969ReviewTableProps = {
    review: C969LinkReview | SectionError | undefined;
    search: string;
};

/**
 * Read-only review of C969 import lines whose saved item differs from the item
 * their product name selects. Nothing is changed here. Hidden when there is
 * nothing to review, so it never shows an unverified alert.
 */
export default function C969ReviewTable({ review, search }: C969ReviewTableProps) {
    if (!review) return null;
    if (isSectionError(review)) {
        return <DashboardSection id="dashboard-c969" title="C969 saved items to review" error={review.error} />;
    }
    if (review.error) {
        return (
            <DashboardSection id="dashboard-c969" title="C969 saved items to review" error={`${review.error}. Details are in the server log`} />
        );
    }
    if (review.count === 0) return null;

    const needle = search.trim().toLowerCase();
    const rows = review.rows.filter(
        (row) => !needle || row.licence_number.toLowerCase().includes(needle) || row.description.toLowerCase().includes(needle),
    );

    return (
        <DashboardSection
            id="dashboard-c969"
            title={`C969 saved items to review (${formatCount(review.count)})`}
            description="Nothing has been changed. Each line's saved item differs from the item its product name selects."
            className="border-amber-300 dark:border-amber-800"
        >
            <div className="max-h-96 overflow-auto">
                <table className="w-full text-sm">
                    <caption className="sr-only">C969 import lines with a saved item to review</caption>
                    <thead className="sticky top-0 z-10 bg-slate-50 dark:bg-slate-900">
                        <tr className="border-b border-slate-200 text-left text-xs font-semibold uppercase tracking-wide text-slate-600 dark:border-slate-800 dark:text-slate-300">
                            <th scope="col" className="px-4 py-2.5">Licence</th>
                            <th scope="col" className="px-4 py-2.5">Import line</th>
                            <th scope="col" className="px-4 py-2.5">Saved item</th>
                            <th scope="col" className="px-4 py-2.5">Expected item</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows.map((row) => (
                            <tr key={row.import_item_id} className="border-t border-slate-200 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-900/50">
                                <td className="px-4 py-2.5 font-medium">
                                    <Link to={licenceEditPath(row.licence_id)} title="Open this licence to correct the saved item" className="rounded-sm text-blue-600 outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring dark:text-blue-400">
                                        {row.licence_number}
                                    </Link>
                                </td>
                                <td className="px-4 py-2.5 text-xs text-slate-900 dark:text-slate-100">{row.description || "—"}</td>
                                <td className="px-4 py-2.5 text-xs text-slate-900 dark:text-slate-100">{row.saved_items.join(", ") || "—"}</td>
                                <td className="px-4 py-2.5 text-xs font-medium text-slate-900 dark:text-slate-100">{row.expected_item}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
            {rows.length === 0 && <p className="p-4 text-sm text-slate-500 dark:text-slate-400">No rows match the search.</p>}
            {review.count > review.rows.length && (
                <p className="px-4 py-2.5 text-xs text-slate-500 dark:text-slate-400">
                    Showing {review.rows.length} of {review.count}.
                </p>
            )}
        </DashboardSection>
    );
}
