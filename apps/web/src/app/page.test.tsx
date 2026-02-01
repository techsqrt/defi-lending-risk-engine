import { describe, it, expect } from "vitest";
import Home from "./page";

describe("Home", () => {
  it("renders without crashing", () => {
    const component = Home();
    expect(component.type).toBe("main");
  });
});
