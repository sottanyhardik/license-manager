import { reportQueryString, type ReportQueryOptions } from "./itemReport/reportQueryString";
export const buildItemReportPath = (options: ReportQueryOptions) => `reports/item-report/?${reportQueryString(options)}`;
export const buildPlannedReportPath = (options: ReportQueryOptions) => `reports/planned-report/?${reportQueryString(options)}`;
