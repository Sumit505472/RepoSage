const OWNER_PATTERN = /^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$/;
const REPOSITORY_PATTERN = /^[A-Za-z0-9_.-]{1,100}$/;

function encodeSegments(value) {
  return value.split("/").map(encodeURIComponent).join("/");
}

export function citationUrl(repository, citation) {
  if (
    !repository ||
    !OWNER_PATTERN.test(repository.owner) ||
    !REPOSITORY_PATTERN.test(repository.name) ||
    typeof repository.branch !== "string" ||
    !repository.branch.trim() ||
    repository.branch.includes("\\") ||
    typeof citation.file_path !== "string" ||
    citation.file_path.startsWith("/") ||
    citation.file_path.includes("\\") ||
    !Number.isInteger(citation.start_line) ||
    !Number.isInteger(citation.end_line) ||
    citation.start_line < 1 ||
    citation.end_line < citation.start_line
  ) {
    return null;
  }

  const branchSegments = repository.branch.split("/");
  const pathSegments = citation.file_path.split("/");
  if (
    [...branchSegments, ...pathSegments].some(
      (segment) => !segment || segment === "." || segment === "..",
    )
  ) {
    return null;
  }

  return `https://github.com/${encodeURIComponent(repository.owner)}/${encodeURIComponent(repository.name)}/blob/${encodeSegments(repository.branch)}/${encodeSegments(citation.file_path)}#L${citation.start_line}-L${citation.end_line}`;
}
