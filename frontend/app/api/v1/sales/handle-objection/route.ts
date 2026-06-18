export const dynamic = "force-dynamic";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function POST(request: Request) {
  const body = await request.json();

  const backendResponse = await fetch(
    `${BACKEND_URL}/api/v1/sales/handle-objection`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: request.headers.get("Authorization") || "",
      },
      body: JSON.stringify(body),
    },
  );

  if (!backendResponse.ok) {
    const errorBody = await backendResponse.text();
    return new Response(errorBody, {
      status: backendResponse.status,
      headers: { "Content-Type": "application/json" },
    });
  }

  return new Response(backendResponse.body, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}
