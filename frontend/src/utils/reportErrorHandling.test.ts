import { describe, expect, it } from "vitest";

import { getReportErrorInfo } from "./reportErrorHandling";

describe("getReportErrorInfo", () => {
  it("reproduces today's exact retryable message when no action is passed (network error, no response)", () => {
    const { message, retryable } = getReportErrorInfo(new Error("Network Error"));

    expect(retryable).toBe(true);
    expect(message).toBe(
      "Unable to load the report. The server is temporarily busy. Please try again in a few seconds.",
    );
  });

  it("reproduces today's exact retryable message when no action is passed (5xx response)", () => {
    const { message, retryable } = getReportErrorInfo({ response: { status: 503 } });

    expect(retryable).toBe(true);
    expect(message).toBe(
      "Unable to load the report. The server is temporarily busy. Please try again in a few seconds.",
    );
  });

  it("substitutes a custom action into the retryable message", () => {
    const { message, retryable } = getReportErrorInfo({ response: { status: 500 } }, { action: "generate the Excel export" });

    expect(retryable).toBe(true);
    expect(message).toBe(
      "Unable to generate the Excel export. The server is temporarily busy. Please try again in a few seconds.",
    );
  });

  it("substitutes a different custom action for the PDF export path", () => {
    const { message, retryable } = getReportErrorInfo({ response: { status: 502 } }, { action: "generate the PDF export" });

    expect(retryable).toBe(true);
    expect(message).toBe(
      "Unable to generate the PDF export. The server is temporarily busy. Please try again in a few seconds.",
    );
  });

  it("is unaffected by `action` for a non-retryable 4xx with a backend message", () => {
    const withoutAction = getReportErrorInfo({ response: { status: 404, data: { error: "No matching licenses." } } });
    const withAction = getReportErrorInfo(
      { response: { status: 404, data: { error: "No matching licenses." } } },
      { action: "generate the Excel export" },
    );

    expect(withoutAction).toEqual({ message: "No matching licenses.", retryable: false });
    expect(withAction).toEqual({ message: "No matching licenses.", retryable: false });
  });

  it("is unaffected by `action` for a non-retryable 4xx with no backend message (generic fallback)", () => {
    const withoutAction = getReportErrorInfo({ response: { status: 400, data: {} } });
    const withAction = getReportErrorInfo({ response: { status: 400, data: {} } }, { action: "generate the PDF export" });

    expect(withoutAction).toEqual({ message: "Something went wrong loading the report.", retryable: false });
    expect(withAction).toEqual({ message: "Something went wrong loading the report.", retryable: false });
  });
});
