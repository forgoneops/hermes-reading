import { host, ROUTES_AREA, SIDEBAR_NAV_AREA, PALETTE_AREA } from '@hermes/plugin-sdk'
import { useEffect, useMemo, useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

const btn = 'inline-flex items-center justify-center gap-2 rounded-lg border border-(--ui-stroke-secondary) bg-(--ui-bg-secondary) px-3 py-2 text-sm text-(--ui-text-primary) transition-colors hover:bg-(--ui-bg-tertiary) disabled:cursor-not-allowed disabled:opacity-50'
const field = 'min-h-10 w-full rounded-lg border border-(--ui-stroke-secondary) bg-(--ui-bg-primary) px-3 py-2 text-sm text-(--ui-text-primary) placeholder:text-(--ui-text-quaternary) outline-none focus:border-(--ui-accent)'
const card = 'rounded-xl border border-(--ui-stroke-secondary) bg-(--ui-bg-secondary)'

const errText = (e) => e instanceof Error ? e.message : String(e)

function ReadingPage({ ctx }) {
  const [tab, setTab] = useState('discover')
  const [data, setData] = useState({ items: [], sources: [], projects: [] })
  const [readings, setReadings] = useState([])
  const [selected, setSelected] = useState(null)
  const [reading, setReading] = useState(null)
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [query, setQuery] = useState('')
  const [url, setUrl] = useState('')
  const [sourceName, setSourceName] = useState('')
  const [sourceUrl, setSourceUrl] = useState('')
  const [language, setLanguage] = useState('')
  const [busy, setBusy] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const load = async (saved = tab === 'saved') => {
    try {
      if (tab === 'history') {
        const result = await ctx.rest('/readings')
        setReadings(result.items || [])
        if (selected?.id) {
          const current = (result.items || []).find((item) => item.id === selected.id)
          if (current) { setSelected(current); setReading(current.content ? { ...current, text: current.content } : null) }
        }
        setError('')
        return
      }
      const result = await ctx.rest(`/feed?q=${encodeURIComponent(query)}&saved=${saved ? 'true' : 'false'}`)
      setData(result)
      setError('')
    } catch (e) { setError(errText(e)) }
  }
  useEffect(() => { void load(tab === 'saved') }, [tab])
  useEffect(() => {
    if (tab !== 'history' || selected?.status !== 'working') return
    const timer = setTimeout(() => void load(false), 2500)
    return () => clearTimeout(timer)
  }, [tab, selected?.status, selected?.step])
  useEffect(() => host.onEvent('plugin.hermes-reading.reading.updated', ({ payload }) => {
    void load(false)
    if (payload?.id === selected?.id) void ctx.rest(`/readings/${selected.id}`).then((item) => { setSelected(item); setReading(item.content ? { ...item, text: item.content } : null) }).catch((e) => setError(errText(e)))
  }), [selected?.id, tab])
  useEffect(() => host.onEvent('plugin.hermes-reading.reading.answer', ({ payload }) => {
    if (payload?.id !== selected?.id) return
    if (payload.error) setError(payload.error)
    else { setAnswer(payload.answer || ''); void load(false) }
  }), [selected?.id])
  useEffect(() => {
    if (tab !== 'projects' || !query.trim()) return
    let active = true
    const timer = setTimeout(async () => {
      setBusy('projects')
      try {
        const result = await ctx.rest(`/projects?q=${encodeURIComponent(query)}&language=${encodeURIComponent(language)}`)
        if (active) setData((old) => ({ ...old, projects: result.items || [] }))
      } catch (e) { if (active) setError(errText(e)) }
      finally { if (active) setBusy('') }
    }, 300)
    return () => { active = false; clearTimeout(timer) }
  }, [tab, query, language])

  const startReading = async (target) => {
    const address = (target || url).trim()
    if (!address) return
    setBusy('read'); setError(''); setMessage('')
    try {
      const result = await host.request('plugin.hermes-reading.reading.start', { url: /^https?:\/\//i.test(address) ? address : `https://${address}` })
      setReading(null); setSelected({ id: result.id, url: address, title: 'Reading source…', status: 'working', step: 'fetching' }); setUrl(''); setTab('history'); setAnswer('')
    } catch (e) { setError(errText(e)) }
    finally { setBusy('') }
  }

  const save = async (item) => {
    setBusy('save'); setError('')
    try {
      await ctx.rest('/save', { method: 'POST', body: { url: item.url, title: item.title || item.url } })
      setMessage('Saved to your reading list.'); await load(tab === 'saved')
    } catch (e) { setError(errText(e)) }
    finally { setBusy('') }
  }

  const askSource = async () => {
    if (!selected?.id || !question.trim()) return
    setBusy('ask'); setError(''); setAnswer('')
    try {
      await host.request('plugin.hermes-reading.reading.ask', { item_id: selected.id, question: question.trim() })
      setMessage('Hermes is answering from this source…'); setQuestion('')
    } catch (e) { setError(errText(e)) }
    finally { setBusy('') }
  }

  const saveNote = async (item) => {
    try {
      const result = await ctx.rest(`/readings/${item.id}/note`, { method: 'POST' })
      setMessage(`Note saved in Hermes Reading · ${result.path.split('/').pop()}`)
      await load(false)
    } catch (e) { setError(errText(e)) }
  }

  const deleteReading = async () => {
    if (!selected?.id) return
    try {
      await ctx.rest(`/readings/${selected.id}`, { method: 'DELETE' })
      setSelected(null); setReading(null); setAnswer(''); setConfirmDelete(false); setMessage('Reading removed.')
      await load(false)
    } catch (e) { setError(errText(e)) }
  }

  const refresh = async () => {
    setBusy('refresh'); setError(''); setMessage('Checking your sources…')
    try {
      const result = await ctx.rest('/refresh', { method: 'POST', timeoutMs: 90000 })
      await load(false)
      setMessage(`${result.updated} items checked${result.failed?.length ? ` · ${result.failed.length} sources unavailable` : ''}.`)
    } catch (e) { setError(errText(e)); setMessage('') }
    finally { setBusy('') }
  }

  const addSource = async (event) => {
    event.preventDefault(); setBusy('source'); setError('')
    try {
      const result = await ctx.rest('/sources', { method: 'POST', body: { name: sourceName, url: sourceUrl } })
      setData((old) => ({ ...old, sources: result.sources })); setSourceName(''); setSourceUrl(''); setMessage('Feed added.');
    } catch (e) { setError(errText(e)) }
    finally { setBusy('') }
  }

  const askHermes = async () => {
    const sessionId = host.state.focusedSessionId.get()
    if (!sessionId) { host.notify({ kind: 'info', message: 'Open a chat first, then ask Hermes to read this item.' }); return }
    const text = reading?.text || selected?.summary || ''
    const prompt = `Read this source and summarize it in Polish. Keep names, dates and numbers exact. Separate what the source states from your interpretation.\n\nTitle: ${selected?.title || reading?.title || ''}\nURL: ${selected?.url || reading?.url || ''}\n\nSOURCE TEXT\n${text.slice(0, 16000)}\nEND SOURCE TEXT`
    try {
      await host.composer.setDraft(sessionId, prompt)
      host.notify({ kind: 'success', message: 'Reading prompt added to the chat draft. Review it and press Send.' })
    } catch (e) { host.notifyError(e, 'Could not add the reading to the chat draft.') }
  }

  const items = useMemo(() => data.items.filter((item) => !query.trim() || `${item.title} ${item.source} ${item.summary}`.toLowerCase().includes(query.trim().toLowerCase())), [data.items, query])
  const tabs = [['discover', 'Discover'], ['projects', 'Projects'], ['history', 'Reading history'], ['saved', 'Reading list'], ['sources', 'Sources']]

  return jsxs('div', { className: 'flex h-full min-h-0 flex-col gap-4 overflow-hidden p-4 text-(--ui-text-primary)', children: [
    jsxs('header', { className: 'flex shrink-0 flex-wrap items-center justify-between gap-3', children: [
      jsxs('div', { children: [jsx('div', { className: 'text-xs text-(--ui-text-tertiary)', children: 'News, papers and reading' }), jsx('h1', { className: 'mt-1 text-2xl font-semibold tracking-tight', children: 'Reading' })] }),
      jsxs('div', { className: 'flex items-center gap-2', children: [
        jsx('button', { type: 'button', className: btn, disabled: !!busy, onClick: () => void refresh(), children: busy === 'refresh' ? 'Refreshing…' : 'Refresh feeds' }),
      ] }),
    ] }),
    jsxs('div', { className: 'flex shrink-0 flex-wrap items-center gap-2', children: [
      tabs.map(([id, label]) => jsx('button', { type: 'button', className: `${btn} ${tab === id ? 'border-(--ui-accent) text-(--ui-accent)' : 'text-(--ui-text-secondary)'}`, 'aria-pressed': tab === id, onClick: () => { setTab(id); setMessage(''); }, children: label }, id)),
      jsx('div', { className: 'min-w-48 flex-1' }),
      jsx('input', { className: `${field} max-w-sm`, value: query, placeholder: 'Search titles and sources…', 'aria-label': 'Search readings', onChange: (e) => setQuery(e.target.value) }),
    ] }),
    jsxs('form', { className: `flex shrink-0 gap-2 p-2 ${card}`, onSubmit: (e) => { e.preventDefault(); void startReading(url) }, children: [
      jsx('input', { className: `${field} border-transparent bg-transparent`, type: 'text', inputMode: 'url', autoCapitalize: 'none', spellCheck: false, value: url, onChange: (e) => setUrl(e.target.value), placeholder: 'Paste an article, PDF, arXiv or YouTube link…', 'aria-label': 'Link to read' }),
      jsx('button', { className: `${btn} border-transparent bg-(--ui-accent) text-white`, type: 'submit', disabled: !url.trim() || !!busy, children: busy === 'read' ? 'Reading…' : 'Read' }),
    ] }),
    message && jsx('div', { className: 'shrink-0 text-sm text-(--ui-text-tertiary)', role: 'status', children: message }),
    error && jsx('div', { className: 'shrink-0 rounded-lg border border-(--ui-error) px-3 py-2 text-sm text-(--ui-error)', role: 'alert', children: error }),
    tab === 'sources' ? jsxs('div', { className: 'min-h-0 flex-1 overflow-y-auto', children: [
      jsxs('section', { className: `${card} grid gap-4 p-4`, children: [
        jsxs('div', { children: [jsx('h2', { className: 'font-medium', children: 'Your sources' }), jsx('p', { className: 'mt-1 text-sm text-(--ui-text-tertiary)', children: `${data.sources.length} feeds · choose sources you want in your daily reading` })] }),
        jsx('div', { className: 'grid gap-2 sm:grid-cols-2', children: data.sources.map((source) => jsxs('div', { className: 'flex min-w-0 items-center justify-between gap-3 rounded-lg border border-(--ui-stroke-secondary) px-3 py-2', children: [jsxs('div', { className: 'min-w-0', children: [jsx('div', { className: 'truncate text-sm font-medium', children: source.name }), jsx('div', { className: 'truncate text-xs text-(--ui-text-tertiary)', children: source.url })] }), jsx('button', { type: 'button', className: btn, onClick: async () => { try { const result = await ctx.rest(`/sources/${source.id}`, { method: 'DELETE' }); setData((old) => ({ ...old, sources: result.sources })) } catch (e) { setError(errText(e)) } }, children: 'Remove' })] }, source.id)) }),
        jsxs('form', { className: 'grid gap-2 border-t border-(--ui-stroke-secondary) pt-4 sm:grid-cols-[1fr_2fr_auto]', onSubmit: addSource, children: [
          jsx('input', { className: field, value: sourceName, onChange: (e) => setSourceName(e.target.value), placeholder: 'Feed name', 'aria-label': 'Feed name' }),
          jsx('input', { className: field, type: 'url', value: sourceUrl, onChange: (e) => setSourceUrl(e.target.value), placeholder: 'https://example.com/feed.xml', 'aria-label': 'RSS or Atom feed URL' }),
          jsx('button', { className: btn, type: 'submit', disabled: !sourceName.trim() || !sourceUrl.trim() || !!busy, children: busy === 'source' ? 'Checking…' : 'Add feed' }),
        ] }),
      ] }),
    ] }) : tab === 'projects' ? jsxs('div', { className: `min-h-0 flex-1 overflow-y-auto p-4 ${card}`, children: [
      jsxs('div', { className: 'mb-4 flex flex-wrap items-center justify-between gap-3', children: [jsx('div', { className: 'text-sm text-(--ui-text-tertiary)', children: query.trim() ? `Public GitHub repositories for “${query}”` : 'Search public GitHub repositories by name or topic.' }), jsx('select', { className: `${field} w-auto`, value: language, 'aria-label': 'Filter GitHub projects by language', onChange: (e) => setLanguage(e.target.value), children: [['', 'Any language'], ['TypeScript', 'TypeScript'], ['Python', 'Python'], ['Rust', 'Rust'], ['Go', 'Go'], ['JavaScript', 'JavaScript']].map(([value, label]) => jsx('option', { value, children: label }, value)) })] }),
      !query.trim() ? jsx('p', { className: 'py-12 text-center text-sm text-(--ui-text-tertiary)', children: 'Enter a project, language or topic in search above.' }) : !(data.projects || []).length ? jsx('p', { className: 'py-12 text-center text-sm text-(--ui-text-tertiary)', children: busy === 'projects' ? 'Searching GitHub…' : 'No repositories found.' }) : jsx('div', { className: 'grid gap-3 md:grid-cols-2', children: data.projects.map((project) => jsxs('article', { className: `${card} p-4`, children: [jsx('a', { className: 'font-medium text-(--ui-accent)', href: project.url, target: '_blank', rel: 'noreferrer noopener', children: project.name }), project.description && jsx('p', { className: 'mt-2 line-clamp-3 text-sm text-(--ui-text-secondary)', children: project.description }), jsxs('div', { className: 'mt-4 flex gap-3 text-xs text-(--ui-text-tertiary)', children: [project.language && jsx('span', { children: project.language }), jsx('span', { children: `★ ${Number(project.stars).toLocaleString()}` })] }), jsx('button', { className: `${btn} mt-3`, type: 'button', onClick: () => void save({ url: project.url, title: project.name }), children: 'Save project' })] }, project.url)) }),
    ] }) : jsxs('div', { className: 'grid min-h-0 flex-1 gap-3 overflow-hidden lg:grid-cols-[minmax(260px,0.8fr)_minmax(0,1.6fr)]', children: [
      jsxs('aside', { className: `min-h-0 overflow-y-auto ${card}`, 'aria-label': tab === 'saved' ? 'Saved readings' : tab === 'history' ? 'Reading history' : 'Discover', children: [
        jsxs('div', { className: 'sticky top-0 flex items-center justify-between border-b border-(--ui-stroke-secondary) bg-(--ui-bg-secondary) px-3 py-2', children: [jsx('span', { className: 'text-xs font-medium text-(--ui-text-tertiary)', children: tab === 'history' ? `HISTORY · ${readings.length}` : tab === 'saved' ? `READING LIST · ${items.length}` : `LATEST · ${items.length}` }), jsx('button', { type: 'button', className: 'text-xs text-(--ui-accent)', onClick: () => void load(tab === 'saved'), children: 'Reload' })] }),
        tab === 'history' ? (!readings.length ? jsx('p', { className: 'p-4 text-sm text-(--ui-text-tertiary)', children: 'Summarized sources appear here, including their history and saved notes.' }) : readings.map((item) => jsxs('button', { type: 'button', className: `block w-full border-b border-(--ui-stroke-secondary) p-3 text-left transition-colors hover:bg-(--ui-bg-tertiary) ${selected?.id === item.id ? 'bg-(--ui-bg-tertiary)' : ''}`, onClick: () => { setSelected(item); setReading(item.content ? { ...item, text: item.content } : null); setAnswer('') }, children: [jsx('span', { className: 'text-[11px] text-(--ui-text-tertiary)', children: `${(item.kind || 'article').toUpperCase()} · ${item.status === 'working' ? item.step || 'working' : item.status}` }), jsx('span', { className: 'mt-1 block text-sm font-medium leading-snug', children: item.title }), item.summary && jsx('span', { className: 'mt-1 line-clamp-2 block text-xs text-(--ui-text-tertiary)', children: item.summary })] }, item.id))) : !items.length ? jsx('p', { className: 'p-4 text-sm text-(--ui-text-tertiary)', children: tab === 'saved' ? 'Your reading list is empty. Save a story or paste a link above.' : 'No stories yet. Refresh your feeds or add a source.' }) : items.map((item) => jsxs('button', { type: 'button', className: `block w-full border-b border-(--ui-stroke-secondary) p-3 text-left transition-colors hover:bg-(--ui-bg-tertiary) ${selected?.url === item.url ? 'bg-(--ui-bg-tertiary)' : ''}`, onClick: () => { setSelected(item); setReading(item.content ? { ...item, text: item.content } : null) }, children: [jsx('span', { className: 'text-[11px] text-(--ui-text-tertiary)', children: item.source }), jsx('span', { className: 'mt-1 block text-sm font-medium leading-snug', children: item.title }), item.summary && jsx('span', { className: 'mt-1 line-clamp-2 block text-xs text-(--ui-text-tertiary)', children: item.summary })] }, item.id)),
      ] }),
      jsxs('article', { className: `min-h-0 overflow-y-auto p-4 sm:p-6 ${card}`, 'aria-live': 'polite', children: [
        !selected ? jsxs('div', { className: 'mx-auto flex h-full max-w-lg flex-col items-center justify-center text-center', children: [jsx('div', { className: 'mb-4 text-3xl text-(--ui-accent)', children: '◉' }), jsx('h2', { className: 'text-lg font-medium', children: 'A quieter place to keep up and read' }), jsx('p', { className: 'mt-2 text-sm text-(--ui-text-tertiary)', children: 'Choose a story on the left or paste a link above. News and long-form reading stay together here.' })] }) : jsxs('div', { className: 'mx-auto max-w-3xl', children: [
          jsx('div', { className: 'text-xs text-(--ui-text-tertiary)', children: selected.source || 'Reading' }),
          jsx('h2', { className: 'mt-2 text-2xl font-semibold leading-tight tracking-tight', children: selected.title || reading?.title || selected.url }),
          jsx('a', { className: 'mt-2 block break-all text-xs text-(--ui-accent)', href: selected.url, target: '_blank', rel: 'noreferrer noopener', children: selected.url }),
          (selected.metadata?.author || selected.metadata?.published || selected.metadata?.site || selected.transcript_method) && jsx('p', { className: 'mt-2 text-xs text-(--ui-text-tertiary)', children: [selected.metadata?.author, selected.metadata?.site, selected.metadata?.published, selected.transcript_method].filter(Boolean).join(' · ') }),
          jsxs('div', { className: 'mt-5 flex flex-wrap gap-2', children: [
            jsx('button', { className: btn, type: 'button', disabled: !!busy || selected.status === 'working', onClick: () => void startReading(selected.url), children: selected.status === 'working' ? `Reading · ${selected.step || 'working'}…` : selected.summary ? 'Summarize again' : 'Read & summarize' }),
            jsx('button', { className: btn, type: 'button', disabled: !!busy, onClick: () => void save(selected), children: selected.saved ? 'Saved' : 'Save for later' }),
            selected.summary && jsx('button', { className: btn, type: 'button', onClick: () => void saveNote(selected), children: selected.note ? 'Save another note' : 'Save Markdown note' }),
            jsx('button', { className: btn, type: 'button', disabled: !reading?.text, onClick: () => void askHermes(), children: 'Draft in chat' }),
            selected.id && tab === 'history' && jsx('button', { className: `${btn} text-(--ui-error)`, type: 'button', onClick: () => setConfirmDelete(true), children: 'Remove' }),
          ] }),
          confirmDelete && jsxs('div', { className: 'mt-3 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-(--ui-error) p-3', role: 'alertdialog', children: [jsx('span', { className: 'text-sm', children: 'Remove from Reading history and saved links? Markdown notes stay in your Hermes Reading data.' }), jsxs('div', { className: 'flex gap-2', children: [jsx('button', { className: btn, type: 'button', onClick: () => setConfirmDelete(false), children: 'Keep it' }), jsx('button', { className: `${btn} border-(--ui-error) text-(--ui-error)`, type: 'button', onClick: () => void deleteReading(), children: 'Remove reading' })] })] }),
          selected.error && jsx('p', { className: 'mt-3 text-sm text-(--ui-error)', role: 'alert', children: selected.error }),
          selected.summary && jsxs('section', { className: 'mt-5 rounded-lg border border-(--ui-stroke-secondary) p-4', children: [jsx('h3', { className: 'text-sm font-semibold', children: 'Summary' }), jsx('div', { className: 'mt-3 whitespace-pre-wrap text-sm leading-relaxed text-(--ui-text-secondary)', children: selected.summary })] }),
          reading?.text && jsxs('section', { className: 'mt-5 border-t border-(--ui-stroke-secondary) pt-4', children: [jsx('h3', { className: 'text-sm font-semibold', children: 'Ask about this source' }), jsx('div', { className: 'mt-2 flex gap-2', children: [jsx('input', { className: field, value: question, onChange: (e) => setQuestion(e.target.value), placeholder: 'Ask a question answered from the source…', 'aria-label': 'Question about source' }), jsx('button', { className: btn, type: 'button', disabled: !question.trim() || !!busy, onClick: () => void askSource(), children: busy === 'ask' ? 'Asking…' : 'Ask' })] }), answer && jsx('p', { className: 'mt-3 whitespace-pre-wrap text-sm leading-relaxed text-(--ui-text-secondary)', children: answer }), (selected.qa || []).map((entry, index) => jsxs('details', { className: 'mt-2 rounded-lg border border-(--ui-stroke-secondary) p-3', children: [jsx('summary', { className: 'cursor-pointer text-sm font-medium', children: entry.q }), jsx('p', { className: 'mt-2 whitespace-pre-wrap text-sm text-(--ui-text-secondary)', children: entry.a })] }, index))] }),
          reading?.text && jsx('section', { className: 'mt-6 border-t border-(--ui-stroke-secondary) pt-5', children: jsxs('details', { children: [jsx('summary', { className: 'cursor-pointer text-sm font-medium', children: 'Extracted text' }), jsx('pre', { className: 'mt-3 whitespace-pre-wrap break-words font-sans text-sm leading-relaxed text-(--ui-text-secondary)', children: reading.text.slice(0, 24000) })] }) }),
        ] }),
      ] }),
    ] }),
  ] })
}

export default {
  id: 'hermes-reading',
  name: 'Reading',
  defaultEnabled: false,
  register(ctx) {
    const render = () => jsx(ReadingPage, { ctx })
    ctx.registerMany([
      { id: 'page', area: ROUTES_AREA, data: { path: '/reading' }, render },
      { id: 'nav', area: SIDEBAR_NAV_AREA, data: { path: '/reading', label: 'Reading', codicon: 'book' } },
      { id: 'open', area: PALETTE_AREA, data: { id: 'hermes-reading.open', label: 'Open Reading', keywords: ['news', 'feed', 'article', 'paper', 'reading', 'github', 'projects'], run: () => host.navigate('/reading') } },
    ])
  },
}
