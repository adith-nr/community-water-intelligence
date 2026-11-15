import { NextRequest } from "next/server";

type Context = { params: Promise<{ path: string[] }> };

async function forward(request: NextRequest, { params }: Context) {
  const { path } = await params;
  const api = process.env.API_URL ?? "http://127.0.0.1:8000";
  const headers = new Headers();
  for (const name of ["authorization", "content-type", "range"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  try {
    const upstream = await fetch(
      `${api}/api/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`,
      {
        method: request.method,
        headers,
        body: request.method === "POST" ? request.body : undefined,
        ...(request.method === "POST" ? { duplex: "half" } : {}),
        cache: "no-store",
        signal: AbortSignal.timeout(85000),
      },
    );
    const resultHeaders = new Headers();
    for (const name of ["content-type", "content-disposition", "accept-ranges", "content-range"]) {
      const value = upstream.headers.get(name);
      if (value) resultHeaders.set(name, value);
    }
    return new Response(upstream.body, { status: upstream.status, headers: resultHeaders });
  } catch {
    return Response.json({ detail: "The pilot API is unavailable." }, { status: 502 });
  }
}

export { forward as GET, forward as POST };
