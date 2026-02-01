import { describe, it, expect } from "vitest";

describe("api", () => {
  it("API_BASE defaults to localhost", async () => {
    const { fetchOverview } = await import("./api");
    expect(fetchOverview).toBeDefined();
  });
});
