async function parseError(r) {
  const text = await r.text()
  let err
  try {
    const j = JSON.parse(text)
    if (j?.error) {
      err = new Error(j.error.message)
      err.code = j.error.code
      err.field = j.error.field
    } else {
      err = new Error(text)
    }
  } catch {
    err = new Error(text || `HTTP ${r.status}`)
  }
  err.status = r.status
  return err
}

async function sendJSON(method, path, body) {
  const r = await fetch(path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!r.ok) throw await parseError(r)
  return r.json()
}

export function getJSON(path) {
  return sendJSON('GET', path)
}
export function postJSON(path, body) {
  return sendJSON('POST', path, body)
}
export function putJSON(path, body) {
  return sendJSON('PUT', path, body)
}
