export async function request(path, options = {}) {
  const r = await fetch(path, options)
  if (!r.ok) {
    let payload = null
    try { payload = await r.json() } catch { /* non-JSON error body */ }
    const err = new Error()
    err.status = r.status
    err.payload = payload
    // 后端业务校验错误：{detail:{code,field,message}}
    if (payload && payload.detail && payload.detail.code) {
      err.code = payload.detail.code
      err.field = payload.detail.field
      err.message = payload.detail.message
    } else if (payload && payload.detail) {
      err.message = typeof payload.detail === 'string' ? payload.detail : JSON.stringify(payload.detail)
    } else {
      err.message = `请求失败 (${r.status})`
    }
    throw err
  }
  return r.json()
}

export function getJSON(path) {
  return request(path)
}
export function postJSON(path, body) {
  return request(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}
export function putJSON(path, body) {
  return request(path, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export function currentPeriod(d = new Date()) {
  const m = String(d.getMonth() + 1).padStart(2, '0')
  return `${d.getFullYear()}-${m}`
}
