/** Display-only names. Stored names, request payloads and exported records stay intact. */
export function projectNameParts(name: string) {
  const [title, ...detail] = name.split(/\s+[·•]\s+/u)
  return { title, detail: detail.join(' · ') }
}

export function schemeNameParts(name: string) {
  const details: string[] = []
  const title = name
    .replace(/[（(](演示自拟|教学演示|教学推演)[）)]/gu, (_, detail: string) => { details.push(detail); return '' })
    .replace(/\s*[·•]\s*(教学推演|教学演示|演示自拟)(?=\s*[·•]|\s*$)/gu, (_, detail: string) => { details.push(detail); return '' })
    .trim()
  return { title, detail: [...new Set(details)].join(' · ') }
}

/** A literal, compact chart label; never infer a structural system from a score or ranking. */
export function shortSchemeLabel(name: string, badge?: string): string {
  const { title } = schemeNameParts(name)
  const code = title.match(/^([A-Z])(?:\s|$)/iu)?.[1] ?? badge
  const type = title.includes('MiC') ? 'MiC'
    : title.includes('框架-剪力墙') || title.includes('框架剪力墙') ? '框架-剪力墙'
    : title.includes('剪力墙') ? '剪力墙'
    : title.includes('钢结构') ? '钢结构'
    : title.replace(/^[A-Z]\s+/iu, '')
  const label = Array.from(type).length > 8 ? Array.from(type).slice(0, 8).join('') + '…' : type
  return code ? `${code} · ${label}` : label
}
