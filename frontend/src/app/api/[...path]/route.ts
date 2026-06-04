import { NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = {
  params: Promise<{ path: string[] }>;
};

const PYTHON_API_BASE_URL = process.env.PYTHON_API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8010/api";

export async function GET(request: NextRequest, context: RouteContext) {
  return proxyToPython(request, context);
}

export async function POST(request: NextRequest, context: RouteContext) {
  return proxyToPython(request, context);
}

export async function PUT(request: NextRequest, context: RouteContext) {
  return proxyToPython(request, context);
}

export async function PATCH(request: NextRequest, context: RouteContext) {
  return proxyToPython(request, context);
}

export async function DELETE(request: NextRequest, context: RouteContext) {
  return proxyToPython(request, context);
}

async function proxyToPython(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  const sourceUrl = new URL(request.url);
  const targetUrl = `${PYTHON_API_BASE_URL.replace(/\/$/, "")}/${path.join("/")}${sourceUrl.search}`;
  const headers = new Headers(request.headers);
  headers.delete("host");
  headers.delete("x-forwarded-host");
  headers.delete("x-forwarded-proto");
  headers.delete("x-forwarded-port");

  const body = request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer();
  const upstream = await fetch(targetUrl, {
    method: request.method,
    headers,
    body,
    cache: "no-store"
  });

  const responseHeaders = new Headers(upstream.headers);
  responseHeaders.delete("content-encoding");
  responseHeaders.delete("content-length");

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders
  });
}
