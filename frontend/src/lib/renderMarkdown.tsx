function inlineParse(s: string): React.ReactNode {
  const parts = s.split(/(\*\*[^*]+\*\*|\[[^\]]+\]\([^)]+\))/)
  return parts.map((p, i) => {
    if (p.startsWith('**') && p.endsWith('**'))
      return <strong key={i}>{p.slice(2, -2)}</strong>
    const link = p.match(/^\[([^\]]+)\]\(([^)]+)\)$/)
    if (link)
      return (
        <a key={i} href={link[2]} target="_blank" rel="noopener noreferrer">
          {link[1]}
        </a>
      )
    return p
  })
}

export function renderMarkdown(text: string): React.ReactNode {
  const lines = text.split('\n')
  const elements: React.ReactNode[] = []
  let listItems: string[] = []
  let key = 0

  const flushList = () => {
    if (listItems.length > 0) {
      elements.push(
        <ul key={key++}>
          {listItems.map((item, i) => <li key={i}>{inlineParse(item)}</li>)}
        </ul>
      )
      listItems = []
    }
  }

  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed) {
      flushList()
      continue
    }
    if (trimmed === '---') {
      flushList()
      elements.push(<hr key={key++} className="scheda-divider" />)
      continue
    }
    if (trimmed.startsWith('### ')) {
      flushList()
      elements.push(<h3 key={key++}>{inlineParse(trimmed.slice(4))}</h3>)
    } else if (trimmed.startsWith('## ')) {
      flushList()
      elements.push(<h2 key={key++}>{inlineParse(trimmed.slice(3))}</h2>)
    } else if (trimmed.startsWith('# ')) {
      flushList()
      elements.push(<h1 key={key++}>{inlineParse(trimmed.slice(2))}</h1>)
    } else if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      listItems.push(trimmed.slice(2))
    } else {
      flushList()
      elements.push(<p key={key++}>{inlineParse(trimmed)}</p>)
    }
  }
  flushList()
  return <>{elements}</>
}
