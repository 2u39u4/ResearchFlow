import { readFileSync } from "fs";
import { join } from "path";
import { NextResponse } from "next/server";

export async function GET() {
  try {
    const path = join(process.cwd(), "..", "examples", "pipeline_report_sample.json");
    const raw = readFileSync(path, "utf-8");
    return NextResponse.json(JSON.parse(raw));
  } catch {
    return NextResponse.json({ error: "Demo not found" }, { status: 404 });
  }
}
