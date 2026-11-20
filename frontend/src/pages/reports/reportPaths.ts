import { reportQueryString, type ReportQueryOptions } from "./itemReport/reportQueryString";
export const buildItemReportPath = (options: ReportQueryOptions) => `reports/item-report/?${reportQueryString(options)}`;
export const buildPlannedReportPath = (options: ReportQueryOptions) => `reports/planned-report/?${reportQueryString(options)}`;
export const buildItemReportProductsPath = (options: ReportQueryOptions) => `reports/item-report/products/?${reportQueryString(options)}`;
export const buildItemReportProductDrilldownPath = (key: string, options: ReportQueryOptions) =>
    `reports/item-report/products/drilldown/?${new URLSearchParams({ key }).toString()}&${reportQueryString(options)}`;
