const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"
).replace(/\/+$/, "");

export class ApiError extends Error {
  constructor(message, status = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function isRecord(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function describeErrorDetail(detail) {
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => (isRecord(item) ? item.msg : null))
      .filter((message) => typeof message === "string");
    if (messages.length) return messages.join("; ");
  }
  return null;
}

async function postJson(path, payload) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new ApiError(
      `Could not reach the RepoSage backend at ${API_BASE_URL}. Check that it is running and try again.`,
    );
  }

  const responseText = await response.text();
  let data;
  try {
    data = JSON.parse(responseText);
  } catch {
    throw new ApiError(
      `The backend returned an invalid response (HTTP ${response.status}).`,
      response.status,
    );
  }

  if (!response.ok) {
    const detail = isRecord(data)
      ? describeErrorDetail(data.detail)
      : null;
    throw new ApiError(
      detail ?? `The request failed with HTTP ${response.status}.`,
      response.status,
    );
  }
  return data;
}

function validateIndexedRepository(data) {
  if (
    !isRecord(data) ||
    typeof data.owner !== "string" ||
    typeof data.name !== "string" ||
    typeof data.branch !== "string" ||
    !Array.isArray(data.files) ||
    !data.files.every(
      (file) =>
        isRecord(file) &&
        typeof file.path === "string" &&
        (typeof file.language === "string" || file.language === null) &&
        typeof file.source === "string",
    )
  ) {
    throw new ApiError("The backend returned an unexpected index response.");
  }
  return data;
}

function validateAnswer(data) {
  if (
    !isRecord(data) ||
    typeof data.repository !== "string" ||
    typeof data.question !== "string" ||
    typeof data.answer !== "string" ||
    typeof data.insufficient_context !== "boolean" ||
    !Array.isArray(data.citations) ||
    !data.citations.every(
      (citation) =>
        isRecord(citation) &&
        typeof citation.source_id === "string" &&
        typeof citation.chunk_id === "string" &&
        typeof citation.file_path === "string" &&
        Number.isInteger(citation.start_line) &&
        Number.isInteger(citation.end_line) &&
        typeof citation.relevant_content === "string",
    )
  ) {
    throw new ApiError("The backend returned an unexpected answer response.");
  }
  return data;
}

export async function indexRepository(repositoryUrl) {
  const response = await postJson("/api/repositories/index", {
    repository_url: repositoryUrl,
  });
  return validateIndexedRepository(response);
}

export async function askRepository(repositoryUrl, question) {
  const response = await postJson("/api/repositories/ask", {
    repository_url: repositoryUrl,
    question,
  });
  return validateAnswer(response);
}

export { API_BASE_URL };
